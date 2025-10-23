#!/usr/bin/env python3
"""
Fetch subnet alpha-token prices (TAO per ALPHA) at a specific timestamp.

Usage:
    python dump_prices_at_block.py --date 2025-10-22 --time 16:00+00:00
"""

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import bittensor as bt


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
        print(f"[warn] Cannot fetch block {block}: {type(e).__name__} ({e})")
        return None

    return None

ESTIMATED_BLOCKS_PER_DAY = 7200


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


def fetch_prices_at_block(sub: bt.Subtensor, block: int):
    infos = sub.get_all_subnets_info(block=block) or []

    def load_price_map() -> dict[int, float | None]:
        try:
            balances = sub.get_subnet_prices(block=block) or {}
            return {int(netuid): balance_to_float(balance) for netuid, balance in balances.items()}
        except Exception as primary_exc:
            print(f"[info] Swap-based price fetch unavailable: {type(primary_exc).__name__} ({primary_exc})")
        try:
            dynamics = sub.all_subnets(block=block) or []
        except Exception as fallback_exc:
            print(f"[warn] Reserve-based price fallback failed: {type(fallback_exc).__name__} ({fallback_exc})")
            return {}
        prices: dict[int, float | None] = {}
        for dynamic in dynamics:
            netuid = int(getattr(dynamic, "netuid", -1))
            prices[netuid] = balance_to_float(getattr(dynamic, "price", None))
        prices[0] = 1.0
        return prices

    price_map = load_price_map()

    rows = []
    for info in infos:
        netuid = int(getattr(info, "netuid"))
        price_tao = price_map.get(netuid)

        rows.append({
            "netuid": netuid,
            #"symbol": getattr(info, "symbol", None),
            #"name": getattr(info, "subnet_name", None),
            "price_tao_per_alpha": price_tao,
        })

    # include any subnets from fallback price map that might not be present in infos
    known_netuid = {row["netuid"] for row in rows}
    for netuid, price in price_map.items():
        if netuid in known_netuid:
            continue
        rows.append({
            "netuid": netuid,
            "price_tao_per_alpha": price,
        })

    rows.sort(key=lambda x: x["netuid"])
    return rows


def parse_requested_datetime(date_str: str, time_str: str) -> datetime:
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M%z")
    except ValueError as exc:
        raise SystemExit(f"Invalid --time format {time_str!r}: {exc}") from exc


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
        default="16:00+00:00",
        help="Time with offset in HH:MM±HH:MM (default: 16:00+00:00)",
    )
    args = parser.parse_args()

    sub = bt.Subtensor(network=args.network)

    if args.date_range:
        start_str, end_str = args.date_range.split(":", maxsplit=1)
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise SystemExit(f"Invalid --date-range format {args.date_range!r}: {exc}") from exc
        if end_date < start_date:
            raise SystemExit("--date-range end must be on or after start")

        output_dir = Path("outputs")
        output_dir.mkdir(parents=True, exist_ok=True)

        prev_block: int | None = None
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            requested_dt = parse_requested_datetime(date_str, args.time)
            target_utc = requested_dt.astimezone(timezone.utc)

            min_block = prev_block
            max_block = prev_block + ESTIMATED_BLOCKS_PER_DAY * 2 if prev_block else None

            print(f"Finding block closest to {target_utc.isoformat()} UTC for {date_str}...")
            block = find_block_at_time(sub, target_utc, min_block=min_block, max_block=max_block)
            block_time = get_block_timestamp(sub, block)

            if block_time is None:
                raise RuntimeError(f"Unable to read timestamp for block {block}")

            if max_block is not None and block_time < target_utc:
                block = find_block_at_time(sub, target_utc)
                block_time = get_block_timestamp(sub, block)
                if block_time is None:
                    raise RuntimeError(f"Unable to read timestamp for block {block}")

            rows = fetch_prices_at_block(sub, block)
            output = {
                "requested_time": requested_dt.isoformat(),
                "closest_block": block,
                "block_timestamp_utc": block_time.isoformat(),
                "network": args.network,
                "prices": rows,
            }

            out_path = output_dir / f"prices_{date_str}.json"
            out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved {out_path} (block {block} at {block_time.isoformat()} UTC)")

            prev_block = block
            current_date += timedelta(days=1)
    else:
        requested_dt = parse_requested_datetime(args.date, args.time)
        target_utc = requested_dt.astimezone(timezone.utc)

        print(f"Finding block closest to {target_utc.isoformat()} UTC...")
        block = find_block_at_time(sub, target_utc)
        block_time = get_block_timestamp(sub, block)
        if block_time is None:
            raise RuntimeError(f"Unable to read timestamp for block {block}")
        print(f"Closest block: {block} at {block_time.isoformat()} UTC")

        rows = fetch_prices_at_block(sub, block)
        output = {
            "requested_time": requested_dt.isoformat(),
            "closest_block": block,
            "block_timestamp_utc": block_time.isoformat(),
            "network": args.network,
            "prices": rows,
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
