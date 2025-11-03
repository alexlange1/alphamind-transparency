#!/usr/bin/env python3
"""
Dump subnet price snapshots for every block across one or more UTC days.

The script finds the midnight block for each requested day (preferably from the
precomputed cache) and then walks block-by-block until the next midnight,
fetching prices concurrently with a worker pool. Results are written as
JSON files named `prices_<YYYY-MM-DD>.json`, matching the layout expected by
`translate_price_dumps.py`. Use `--block-step` to sample every Nth block and
`--block-offset` to skip an initial number of blocks from midnight.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import local
from typing import Any, Dict, Iterable, List, Optional, Tuple

import bittensor as bt
from async_substrate_interface.errors import SubstrateRequestException

COLLECTION_METHOD = "btsdk scripts v2 / per-block"
DEFAULT_MIDNIGHT_BLOCK_FILE = Path(__file__).with_name("midnight_blocks.json")

_THREAD_STATE = local()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def log(message: str, *, level: str = "info") -> None:
    prefix = f"[{level}] " if level else ""
    print(f"{prefix}{message}", file=sys.stderr)


def balance_to_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    maybe_tao = getattr(value, "tao", None)
    if isinstance(maybe_tao, (int, float)):
        return float(maybe_tao)
    try:
        return float(value)
    except Exception:
        return None


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid date {value!r}: {exc}") from exc


def daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        log(f"Failed to read JSON from {path}: {exc}", level="warn")
        return {}


def load_midnight_block_map(path: Path, network: str) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    if not payload:
        log(f"No midnight block map found at {path}; falling back to live search.", level="info")
        return {}
    file_network = payload.get("network")
    if file_network and file_network != network:
        log(
            f"Midnight block map {path} targets {file_network}; continuing with available entries.",
            level="warn",
        )
    blocks_raw = payload.get("blocks") or payload.get("block_map") or {}
    if not isinstance(blocks_raw, dict):
        log(f"Midnight block map {path} is missing a 'blocks' dictionary.", level="warn")
        return {}
    blocks: dict[str, dict[str, Any]] = {}
    for key, entry in blocks_raw.items():
        try:
            if isinstance(entry, dict):
                block_val = int(entry.get("block"))
                timestamp_val = entry.get("block_timestamp_utc") or entry.get("timestamp_utc")
            else:
                block_val = int(entry)
                timestamp_val = None
        except (TypeError, ValueError):
            continue
        blocks[key] = {
            "block": block_val,
            "block_timestamp_utc": timestamp_val,
        }
    return blocks


# ---------------------------------------------------------------------------
# Subtensor helpers
# ---------------------------------------------------------------------------
def get_primary_subtensor(network: str) -> bt.Subtensor:
    try:
        return bt.Subtensor(network=network)
    except Exception as exc:
        raise SystemExit(f"Failed to connect to subtensor ({network}): {exc}") from exc


def get_worker_subtensor(network: str, fallback: bt.Subtensor) -> bt.Subtensor:
    if getattr(_THREAD_STATE, "subtensor", None) is None:
        try:
            _THREAD_STATE.subtensor = bt.Subtensor(network=network)
        except Exception as exc:
            log(f"Worker subtensor init failed ({exc}); reusing primary connection.", level="warn")
            _THREAD_STATE.subtensor = fallback
    return _THREAD_STATE.subtensor


def get_block_timestamp(sub: bt.Subtensor, block: int) -> Optional[datetime]:
    try:
        block_hash = sub.substrate.get_block_hash(block)
        if block_hash is None:
            return None
        block_data = sub.substrate.get_block(block_hash)
    except Exception as exc:
        log(f"Cannot fetch block {block}: {type(exc).__name__} ({exc})", level="warn")
        return None

    extrinsics = block_data.get("extrinsics", [])
    for ext in extrinsics:
        if isinstance(ext, dict):
            call = ext.get("call")
        elif hasattr(ext, "value"):
            call = getattr(ext, "value", {}).get("call")
        elif hasattr(ext, "call"):
            call = ext.call
        else:
            call = None
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
    return None


def find_block_at_time(
    sub: bt.Subtensor,
    target_time_utc: datetime,
    min_block: Optional[int] = None,
    max_block: Optional[int] = None,
) -> int:
    """Binary search for the earliest block at or after target_time_utc."""
    latest = max_block if max_block is not None else sub.get_current_block()
    earliest = min_block if min_block is not None else 1
    earliest = max(earliest, 1)

    if latest < earliest:
        latest = sub.get_current_block()

    ts_latest = get_block_timestamp(sub, latest)
    if ts_latest is None:
        if max_block is not None:
            return find_block_at_time(sub, target_time_utc)
        raise RuntimeError("Cannot read latest block timestamp.")

    def find_first_available() -> Tuple[int, datetime]:
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

    earliest, ts_earliest = find_first_available()
    if target_time_utc <= ts_earliest:
        return earliest
    if target_time_utc >= ts_latest:
        if max_block is not None and max_block != sub.get_current_block():
            return find_block_at_time(sub, target_time_utc)
        return latest

    low, high = earliest, latest
    while low < high:
        mid = (low + high) // 2
        ts_mid = get_block_timestamp(sub, mid)
        if ts_mid is None:
            low = mid + 1
            continue
        if ts_mid < target_time_utc:
            low = mid + 1
        else:
            high = mid
    return low


def fetch_prices_at_block(sub: bt.Subtensor, block: int) -> List[Dict[str, Any]]:
    try:
        infos = sub.get_all_subnets_info(block=block) or []
    except Exception as exc:
        log(f"get_all_subnets_info unavailable at block {block}: {exc}", level="warn")
        infos = []

    def load_price_map() -> Dict[int, Optional[float]]:
        try:
            balances = sub.get_subnet_prices(block=block) or {}
            return {int(netuid): balance_to_float(value) for netuid, value in balances.items()}
        except Exception as primary_exc:
            log(
                f"Swap-based price fetch unavailable at block {block}: {type(primary_exc).__name__} ({primary_exc})",
                level="info",
            )
        try:
            dynamics = sub.all_subnets(block=block) or []
        except SubstrateRequestException as fallback_exc:
            log(
                f"Reserve-based price fallback failed at block {block}: {type(fallback_exc).__name__} ({fallback_exc})",
                level="warn",
            )
            return {0: 1.0}

        prices: Dict[int, Optional[float]] = {}
        for item in dynamics:
            netuid = int(getattr(item, "netuid", -1))
            prices[netuid] = balance_to_float(getattr(item, "price", None))
        prices[0] = 1.0
        return prices

    price_map = load_price_map()

    rows: List[Dict[str, Any]] = []
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

    known = {row["netuid"] for row in rows}
    for netuid, price in price_map.items():
        if netuid in known:
            continue
        rows.append(
            {
                "netuid": int(netuid),
                "price_tao_per_alpha": price,
            }
        )

    rows.sort(key=lambda item: item["netuid"])
    return rows


def sanitize_emissions(prices: Iterable[Dict[str, Any]]) -> OrderedDict[str, float]:
    sanitized: Dict[int, float] = {}
    for entry in prices:
        netuid = entry.get("netuid")
        price = entry.get("price_tao_per_alpha")
        if not isinstance(netuid, int) or netuid == 0:
            continue
        if isinstance(price, (int, float)):
            sanitized[netuid] = float(price)
    return OrderedDict((str(netuid), sanitized[netuid]) for netuid in sorted(sanitized))


def compute_statistics(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            "active_subnets": 0,
            "avg_emission_rate": None,
            "max_emission_rate": None,
            "min_emission_rate": None,
            "total_emission_rate": 0.0,
        }
    total = float(sum(values))
    active = len(values)
    return {
        "active_subnets": active,
        "avg_emission_rate": total / active if active else None,
        "max_emission_rate": max(values),
        "min_emission_rate": min(values),
        "total_emission_rate": total,
    }


def build_summary(samples: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if len(samples) < 2:
        return None
    actives = [s["statistics"]["active_subnets"] for s in samples if s["statistics"]["active_subnets"] is not None]
    totals = [s["statistics"]["total_emission_rate"] for s in samples if s["statistics"]["total_emission_rate"] is not None]
    if not actives and not totals:
        return None
    summary: Dict[str, Any] = {"observations": len(samples)}
    if actives:
        summary["active_subnets_min"] = min(actives)
        summary["active_subnets_max"] = max(actives)
    if totals:
        summary["total_emission_rate_min"] = min(totals)
        summary["total_emission_rate_max"] = max(totals)
        summary["total_emission_rate_avg"] = sum(totals) / len(totals)
    return summary


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------
def fetch_block_sample(block: int, network: str, primary_sub: bt.Subtensor) -> Optional[Dict[str, Any]]:
    sub = get_worker_subtensor(network, primary_sub)
    timestamp = get_block_timestamp(sub, block)
    prices = fetch_prices_at_block(sub, block)
    emissions = sanitize_emissions(prices)
    stats = compute_statistics(list(emissions.values()))

    return {
        "closest_block": block,
        "block_timestamp_utc": timestamp.isoformat() if isinstance(timestamp, datetime) else None,
        "requested_time": timestamp.isoformat() if isinstance(timestamp, datetime) else None,
        "prices": prices,
        "emissions": emissions,
        "statistics": stats,
    }


def collect_block_samples(
    start_block: int,
    end_block: int,
    *,
    network: str,
    workers: int,
    primary_sub: bt.Subtensor,
    step: int,
) -> List[Dict[str, Any]]:
    if end_block <= start_block:
        return []

    blocks = list(range(start_block, end_block, max(1, step)))
    if not blocks:
        return []
    samples: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(fetch_block_sample, block, network, primary_sub): block for block in blocks
        }
        for future in as_completed(futures):
            block = futures[future]
            try:
                sample = future.result()
                if sample:
                    sample["sample_index"] = block - start_block
                    samples.append(sample)
            except Exception as exc:
                log(f"Failed to fetch block {block}: {exc}", level="warn")

    samples.sort(key=lambda item: item["closest_block"])
    for index, sample in enumerate(samples):
        sample["sample_index"] = index
    return samples


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------
def build_metadata(
    day: date,
    samples: List[Dict[str, Any]],
    *,
    network: str,
) -> Dict[str, Any]:
    primary = samples[0]
    return {
        "collection_method": COLLECTION_METHOD,
        "date": day.strftime("%Y%m%d"),
        "network": network,
        "timestamp": primary.get("block_timestamp_utc"),
        "closest_block": primary.get("closest_block"),
        "requested_time": primary.get("requested_time"),
        "samples_per_day": len(samples),
        "primary_sample_index": primary.get("sample_index", 0),
    }


def build_daily_output(
    day: date,
    samples: List[Dict[str, Any]],
    *,
    network: str,
) -> Dict[str, Any]:
    metadata = build_metadata(day, samples, network=network)
    summary = build_summary(samples)
    output: Dict[str, Any] = {
        "metadata": metadata,
        "statistics": samples[0]["statistics"],
        "samples": samples,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if summary:
        output["summary"] = summary
    return output


def write_daily_output(base_dir: Path, day: date, payload: Dict[str, Any]) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"prices_{day.strftime('%Y-%m-%d')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Wrote {path}", level="info")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def determine_day_bounds(
    sub: bt.Subtensor,
    *,
    days: List[date],
    midnight_blocks: dict[str, dict[str, Any]],
) -> Dict[date, int]:
    bounds: Dict[date, int] = {}
    for day in days:
        key = day.strftime("%Y-%m-%d")
        entry = midnight_blocks.get(key)
        if entry and isinstance(entry.get("block"), int):
            bounds[day] = int(entry["block"])
            continue
        target = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
        log(f"Finding midnight block for {key} via binary search...", level="info")
        bounds[day] = find_block_at_time(sub, target)
    return bounds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dump subnet prices for every block across one or more UTC days.",
    )
    parser.add_argument("--network", default="finney", help="Bittensor network or endpoint (default: finney)")
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--date", help="Single UTC day (YYYY-MM-DD)")
    date_group.add_argument(
        "--date-range",
        help="Inclusive date range YYYY-MM-DD:YYYY-MM-DD",
    )
    parser.add_argument(
        "--midnight-blocks",
        default=str(DEFAULT_MIDNIGHT_BLOCK_FILE),
        help="Path to midnight block cache (default: ./midnight_blocks.json)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent block fetchers (default: 4)",
    )
    parser.add_argument(
        "--block-step",
        type=int,
        default=1,
        help="Process every Nth block (default: 1 → every block).",
    )
    parser.add_argument(
        "--block-offset",
        type=int,
        default=0,
        help="Block offset from the day’s midnight block before sampling begins (default: 0).",
    )
    parser.add_argument(
        "--output",
        help="Destination JSON path (single-date mode only).",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for auto-named JSON files (default: outputs).",
    )
    args = parser.parse_args()

    if args.date:
        target_days = [parse_date(args.date)]
    else:
        start_str, end_str = args.date_range.split(":", maxsplit=1)
        start_day = parse_date(start_str)
        end_day = parse_date(end_str)
        if end_day < start_day:
            raise SystemExit("--date-range end must be on or after start")
        target_days = list(daterange(start_day, end_day))

    midnight_path = Path(args.midnight_blocks)
    if not midnight_path.is_absolute():
        midnight_path = Path(__file__).resolve().parent / midnight_path
    midnight_blocks = load_midnight_block_map(midnight_path, args.network)

    primary_sub = get_primary_subtensor(args.network)

    if args.block_step < 1:
        raise SystemExit("--block-step must be >= 1")
    if args.block_offset < 0:
        raise SystemExit("--block-offset must be >= 0")

    day_bounds = determine_day_bounds(primary_sub, days=target_days, midnight_blocks=midnight_blocks)

    # Determine boundary block after final day.
    final_day = target_days[-1] + timedelta(days=1)
    final_key = final_day.strftime("%Y-%m-%d")
    final_entry = midnight_blocks.get(final_key)
    if final_entry and isinstance(final_entry.get("block"), int):
        next_block = int(final_entry["block"])
    else:
        target_dt = datetime.combine(final_day, datetime.min.time()).replace(tzinfo=timezone.utc)
        log(f"Finding midnight block for {final_key} via binary search...", level="info")
        next_block = find_block_at_time(primary_sub, target_dt, min_block=day_bounds[target_days[-1]])

    for idx, day in enumerate(target_days):
        start_block = day_bounds[day]
        end_block = next_block if idx == len(target_days) - 1 else day_bounds[target_days[idx + 1]]

        effective_start = start_block + args.block_offset
        if effective_start >= end_block:
            log(
                f"Offset skips entire range for {day}: start {start_block}, offset {args.block_offset}, end {end_block}.",
                level="warn",
            )
            continue

        log(
            f"Processing {day} blocks [{effective_start}, {end_block}) step {args.block_step}",
            level="info",
        )
        samples = collect_block_samples(
            effective_start,
            end_block,
            network=args.network,
            workers=args.workers,
            primary_sub=primary_sub,
            step=args.block_step,
        )
        if not samples:
            log(f"No samples produced for {day}; skipping file.", level="warn")
            continue
        payload = build_daily_output(day, samples, network=args.network)

        if args.date:
            if args.output:
                destination = Path(args.output)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                log(f"Wrote {destination}", level="info")
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        output_dir = Path(args.output_dir or "outputs")
        write_daily_output(output_dir, day, payload)

    log("Completed block dump for requested range.", level="info")


if __name__ == "__main__":
    main()
