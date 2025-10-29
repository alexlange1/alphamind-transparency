#!/usr/bin/env python3
"""
Fetch subnet alpha-token prices (TAO per ALPHA) at a specific timestamp.

Usage:
    python dump_prices_at_block.py --date 2025-10-22 --time 16:00+00:00
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Tuple

import bittensor as bt
from concurrent.futures import ThreadPoolExecutor
from async_substrate_interface.errors import SubstrateRequestException
from threading import local


def get_block_timestamp(sub, block: int) -> datetime | None:
    """Return UTC datetime of a given block.
    If the node pruned the state or the block cannot be fetched, return None.
    """
    try:
        block_hash = sub.substrate.get_block_hash(block)
        if block_hash is None:
            return None

        block_data = sub.substrate.get_block(block_hash)
        extrinsics = block_data.get("extrinsics", [])
        for ext in extrinsics:
            call = None
            if isinstance(ext, dict):
                call = ext.get("call")
            elif hasattr(ext, "value"):
                call = ext.value.get("call")
            elif hasattr(ext, "call"):
                call = ext.call

            if not call:
                continue

            module = call.get("call_module") or call.get("call_module_name")
            if module != "Timestamp":
                continue

            args = call.get("call_args") or call.get("params") or []
            for arg in args:
                value = arg.get("value")
                if isinstance(value, dict) and "value" in value:
                    value = value["value"]
                if isinstance(value, (int, float)):
                    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    except Exception as e:
        # StateDiscardedError or anything else — skip gracefully
        log(f"Cannot fetch block {block}: {type(e).__name__} ({e})", level="warn")
        return None

    return None

ESTIMATED_BLOCKS_PER_DAY = 7200
AVERAGE_BLOCK_SECONDS = 24 * 3600 / ESTIMATED_BLOCKS_PER_DAY
DEFAULT_MIDNIGHT_BLOCK_FILE = Path(__file__).with_name("midnight_blocks.json")


def find_block_at_time(
    sub,
    target_time_utc: datetime,
    min_block: int | None = None,
    max_block: int | None = None,
) -> int:
    """Binary search for block closest to target_time_utc.
    Skips missing (pruned) blocks gracefully.
    """
    latest = max_block if max_block is not None else sub.get_current_block()
    earliest = min_block if min_block is not None else 1
    earliest = max(earliest, 1)

    if latest < earliest:
        latest = sub.get_current_block()

    ts_latest = get_block_timestamp(sub, latest)
    if ts_latest is None:
        if max_block is not None:
            # fall back to full-range search if limited window has no data
            return find_block_at_time(sub, target_time_utc)
        raise RuntimeError("Cannot read latest block timestamp.")

    # Find first block that still has state available on this node
    def find_first_available_block() -> tuple[int, datetime]:
        low, high = earliest, latest
        first_block = None
        first_ts = None

        while low <= high:
            mid = (low + high) // 2
            ts_mid = get_block_timestamp(sub, mid)
            if ts_mid is None:
                low = mid + 1
                continue
            first_block = mid
            first_ts = ts_mid
            high = mid - 1

        if first_block is None or first_ts is None:
            raise RuntimeError("No retrievable blocks on this node.")
        return first_block, first_ts

    earliest, ts_earliest = find_first_available_block()

    if target_time_utc <= ts_earliest:
        return earliest
    if target_time_utc >= ts_latest:
        if max_block is not None and max_block != sub.get_current_block():
            # window too low, redo with full search
            return find_block_at_time(sub, target_time_utc)
        return latest

    low, high = earliest, latest
    while low < high:
        mid = (low + high) // 2
        ts_mid = get_block_timestamp(sub, mid)
        if ts_mid is None:
            # skip if timestamp unavailable
            low = mid + 1
            continue
        if ts_mid < target_time_utc:
            low = mid + 1
        else:
            high = mid
    return low

def balance_to_float(bal):
    if bal is None:
        return None
    try:
        return float(bal)
    except Exception:
        return float(getattr(bal, "tao", 0))


def log(message: str, *, level: str = "info") -> None:
    prefix = f"[{level}] " if level else ""
    print(f"{prefix}{message}", file=sys.stderr)


def fetch_prices_at_block(sub: bt.Subtensor, block: int) -> list[dict[str, Any]]:
    try:
        infos = sub.get_all_subnets_info(block=block) or []
    except SubstrateRequestException as exc:
        log(f"get_all_subnets_info unavailable at block {block}: {exc}", level="warn")
        infos = []

    def load_price_map() -> dict[int, float | None]:
        try:
            balances = sub.get_subnet_prices(block=block) or {}
            return {int(netuid): balance_to_float(balance) for netuid, balance in balances.items()}
        except Exception as primary_exc:
            log(
                f"Swap-based price fetch unavailable: {type(primary_exc).__name__} ({primary_exc})",
                level="info",
            )
        try:
            dynamics = sub.all_subnets(block=block) or []
        except Exception as fallback_exc:
            log(
                f"Reserve-based price fallback failed: {type(fallback_exc).__name__} ({fallback_exc})",
                level="warn",
            )
            return {}
        prices: dict[int, float | None] = {}
        for dynamic in dynamics:
            netuid = int(getattr(dynamic, "netuid", -1))
            prices[netuid] = balance_to_float(getattr(dynamic, "price", None))
        prices[0] = 1.0
        return prices

    price_map = load_price_map()

    rows: list[dict[str, Any]] = []
    for info in infos:
        try:
            netuid = int(getattr(info, "netuid"))
        except Exception:
            continue
        rows.append(
            {
                "netuid": netuid,
                "price_tao_per_alpha": price_map.get(netuid),
            }
        )

    known_netuid = {row["netuid"] for row in rows}
    for raw_netuid, price in price_map.items():
        netuid = int(raw_netuid)
        if netuid in known_netuid:
            continue
        rows.append(
            {
                "netuid": netuid,
                "price_tao_per_alpha": price,
            }
        )

    rows.sort(key=lambda x: x["netuid"])
    return rows


def parse_requested_datetime(date_str: str, time_str: str) -> datetime:
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M%z")
    except ValueError as exc:
        raise SystemExit(f"Invalid --time format {time_str!r}: {exc}") from exc


def build_daily_sample_datetimes(date_str: str, time_str: str, samples_per_day: int) -> list[datetime]:
    if samples_per_day <= 0:
        raise SystemExit("--samples-per-day must be a positive integer")

    base_dt = parse_requested_datetime(date_str, time_str)
    if samples_per_day == 1:
        return [base_dt]

    interval_seconds = 24 * 3600 / samples_per_day
    interval = timedelta(seconds=interval_seconds)
    return [base_dt + i * interval for i in range(samples_per_day)]
 
 
def load_midnight_block_map(path: Path, network: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        log(f"No midnight block map found at {path}; falling back to live search.", level="info")
        return {}

    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        log(f"Failed to read midnight block map {path}: {exc}", level="warn")
        return {}

    file_network = data.get("network")
    if file_network and file_network != network:
        log(
            f"Midnight block map {path} was generated for network {file_network}; continuing with available entries.",
            level="warn",
        )

    raw_blocks = data.get("blocks") or data.get("block_map") or {}
    if not isinstance(raw_blocks, dict):
        log(f"Midnight block map {path} is missing 'blocks' dictionary.", level="warn")
        return {}

    blocks: dict[str, dict[str, Any]] = {}
    for date_key, entry in raw_blocks.items():
        try:
            if isinstance(entry, dict):
                block_val = int(entry.get("block"))
                timestamp_val = entry.get("block_timestamp_utc") or entry.get("timestamp_utc")
            else:
                block_val = int(entry)
                timestamp_val = None
        except (TypeError, ValueError):
            continue
        blocks[date_key] = {
            "block": block_val,
            "block_timestamp_utc": timestamp_val,
        }
    return blocks


def store_midnight_block(
    blocks: dict[str, dict[str, Any]],
    date_key: str,
    block: int,
    block_time: datetime | None,
    *,
    dirty_set: set[str],
) -> None:
    stored_ts = block_time.isoformat() if isinstance(block_time, datetime) else None
    previous = blocks.get(date_key)
    if previous and previous.get("block") == block and previous.get("block_timestamp_utc") == stored_ts:
        return
    blocks[date_key] = {
        "block": int(block),
        "block_timestamp_utc": stored_ts,
    }
    dirty_set.add(date_key)


def save_midnight_block_map(path: Path, network: str, blocks: dict[str, dict[str, Any]]) -> None:
    if not blocks:
        return
    sorted_dates = sorted(blocks)
    payload = {
        "network": network,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": sorted_dates[0],
        "end_date": sorted_dates[-1],
        "blocks": {date_key: blocks[date_key] for date_key in sorted_dates},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Updated midnight block cache at {path}", level="info")


def build_sample_payload(subtensor: bt.Subtensor, requested_dt: datetime, block: int, block_time: datetime | None) -> dict[str, Any]:
    rows = fetch_prices_at_block(subtensor, block)
    timestamp = block_time.isoformat() if isinstance(block_time, datetime) else None
    return {
        "requested_time": requested_dt.isoformat(),
        "closest_block": block,
        "block_timestamp_utc": timestamp,
        "prices": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", default="finney", help="Bittensor network (default: finney)")
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--date", help="Single date in YYYY-MM-DD")
    date_group.add_argument(
        "--date-range",
        help="Date range inclusive in YYYY-MM-DD:YYYY-MM-DD",
    )
    parser.add_argument(
        "--time",
        default="00:00+00:00",
        help="Time with offset in HH:MM±HH:MM (default: 00:00+00:00)",
    )
    parser.add_argument(
        "--output",
        help="Write JSON to this path instead of stdout (single-date mode only).",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for auto-named JSON output (default: outputs in date-range mode).",
    )
    parser.add_argument(
        "--samples-per-day",
        type=int,
        default=1,
        help="Number of evenly spaced snapshots per day (default: 1).",
    )
    parser.add_argument(
        "--sample-workers",
        type=int,
        default=4,
        help="Concurrent samples per day (default: 4).",
    )
    parser.add_argument(
        "--midnight-blocks",
        default=str(DEFAULT_MIDNIGHT_BLOCK_FILE),
        help="Path to JSON file with precomputed midnight blocks (default: ./midnight_blocks.json).",
    )
    args = parser.parse_args()

    samples_per_day = args.samples_per_day
    if samples_per_day < 1:
        raise SystemExit("--samples-per-day must be a positive integer")

    sample_workers = max(1, args.sample_workers)
    sub = bt.Subtensor(network=args.network)

    sample_thread_state = local()
    midnight_blocks: dict[str, dict[str, Any]] = {}
    midnight_dirty: set[str] = set()
    midnight_path: Path | None = None
    if args.midnight_blocks:
        midnight_path = Path(args.midnight_blocks)
        if not midnight_path.is_absolute():
            midnight_path = Path(__file__).resolve().parent / midnight_path
        midnight_blocks = load_midnight_block_map(midnight_path, args.network)

    def get_sample_subtensor() -> bt.Subtensor:
        if sample_workers <= 1:
            return sub
        worker_sub = getattr(sample_thread_state, "subtensor", None)
        if worker_sub is None:
            try:
                worker_sub = bt.Subtensor(network=args.network)
            except Exception as exc:
                log(f'Worker subtensor init failed ({exc}); reusing primary connection.', level='warn')
                worker_sub = sub
            sample_thread_state.subtensor = worker_sub
        return worker_sub

    def build_estimated_sample(
        sample_index: int,
        requested_dt: datetime,
        base_reference_utc: datetime,
        base_block: int,
    ) -> tuple[int, dict[str, Any]]:
        local_sub = get_sample_subtensor()
        target_utc = requested_dt.astimezone(timezone.utc)
        delta_seconds = (target_utc - base_reference_utc).total_seconds()
        estimated_block = int(round(base_block + delta_seconds / AVERAGE_BLOCK_SECONDS))
        if estimated_block < 1:
            estimated_block = 1
        log(
            f"Estimating block {estimated_block} for sample {sample_index + 1}/{samples_per_day} at {target_utc.isoformat()} UTC",
            level="info",
        )
        block_time = get_block_timestamp(local_sub, estimated_block)
        if block_time is None:
            log(
                f"Timestamp unavailable for estimated block {estimated_block} (sample {sample_index + 1})",
                level="warn",
            )
        payload = build_sample_payload(local_sub, requested_dt, estimated_block, block_time)
        return sample_index, payload

    def generate_day_output(date_str: str) -> dict[str, Any]:
        daily_datetimes = build_daily_sample_datetimes(date_str, args.time, samples_per_day)
        base_dt = daily_datetimes[0]
        base_target_utc = base_dt.astimezone(timezone.utc)

        midnight_entry = midnight_blocks.get(date_str)
        target_is_midnight = (
            base_target_utc.hour == 0
            and base_target_utc.minute == 0
            and base_target_utc.second == 0
            and base_target_utc.microsecond == 0
        )

        base_block: int | None = None
        base_block_time: datetime | None = None

        if midnight_entry and target_is_midnight:
            base_block = int(midnight_entry["block"])
            log(
                f"Using precomputed midnight block {base_block} for sample 1/{samples_per_day} ({date_str}).",
                level="info",
            )
            ts_value = midnight_entry.get("block_timestamp_utc")
            if ts_value:
                try:
                    base_block_time = datetime.fromisoformat(ts_value)
                except ValueError:
                    base_block_time = None
            if base_block_time is None:
                base_block_time = get_block_timestamp(sub, base_block)
                if base_block_time is None:
                    log(
                        f"Timestamp unavailable for precomputed block {base_block} ({date_str}); continuing.",
                        level="warn",
                    )
        else:
            log(
                f"Finding block closest to {base_target_utc.isoformat()} UTC for sample 1/{samples_per_day} ({date_str})...",
                level="info",
            )
            base_block = find_block_at_time(sub, base_target_utc)
            base_block_time = get_block_timestamp(sub, base_block)
            if base_block_time is None:
                raise RuntimeError(f"Unable to read timestamp for block {base_block}")

        if target_is_midnight and midnight_path is not None:
            store_midnight_block(
                midnight_blocks,
                date_str,
                base_block,
                base_block_time if isinstance(base_block_time, datetime) else None,
                dirty_set=midnight_dirty,
            )

        if isinstance(base_block_time, datetime):
            log(
                f"Sample 1/{samples_per_day} uses block {base_block} at {base_block_time.isoformat()} UTC",
                level="info",
            )
        else:
            log(
                f"Sample 1/{samples_per_day} uses block {base_block} (timestamp unavailable)",
                level="info",
            )
        base_reference_utc = base_block_time if isinstance(base_block_time, datetime) else base_target_utc

        samples_map: dict[int, dict[str, Any]] = {}
        samples_map[0] = build_sample_payload(sub, base_dt, base_block, base_block_time)

        if samples_per_day > 1:
            follow_up = list(enumerate(daily_datetimes[1:], start=1))
            if sample_workers == 1:
                for index, requested_dt in follow_up:
                    _, payload = build_estimated_sample(index, requested_dt, base_reference_utc, base_block)
                    samples_map[index] = payload
            else:
                with ThreadPoolExecutor(max_workers=sample_workers) as executor:
                    futures = [
                        executor.submit(
                            build_estimated_sample,
                            index,
                            requested_dt,
                            base_reference_utc,
                            base_block,
                        )
                        for index, requested_dt in follow_up
                    ]
                    for future in futures:
                        index, payload = future.result()
                        samples_map[index] = payload

        ordered_samples = [samples_map[idx] for idx in sorted(samples_map)]
        day_output: dict[str, Any] = {
            "date": date_str,
            "network": args.network,
            "samples_per_day": samples_per_day,
            "samples": ordered_samples,
        }
        if samples_per_day == 1:
            day_output.update(ordered_samples[0])
        return day_output

    if args.date_range:
        start_str, end_str = args.date_range.split(":", maxsplit=1)
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise SystemExit(f"Invalid --date-range format {args.date_range!r}: {exc}") from exc
        if end_date < start_date:
            raise SystemExit("--date-range end must be on or after start")

        output_dir = Path(args.output_dir or "outputs")
        output_dir.mkdir(parents=True, exist_ok=True)

        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            day_output = generate_day_output(date_str)
            out_path = output_dir / f"prices_{date_str}.json"
            out_path.write_text(json.dumps(day_output, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"Saved {out_path}", level="info")
            current_date += timedelta(days=1)
    else:
        date_str = args.date
        day_output = generate_day_output(date_str)

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(day_output, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"Saved {out_path}", level="info")
        elif args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"prices_{date_str}.json"
            out_path.write_text(json.dumps(day_output, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"Saved {out_path}", level="info")
        else:
            print(json.dumps(day_output, ensure_ascii=False, indent=2))

    if midnight_path is not None and midnight_dirty:
        save_midnight_block_map(midnight_path, args.network, midnight_blocks)

if __name__ == "__main__":
    main()
