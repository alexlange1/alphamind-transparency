#!/usr/bin/env python3
"""
Cache tracked validator placements at daily midnight blocks.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import bittensor as bt

DEFAULT_COLDKEYS: Tuple[str, ...] = (
    "5HBtpwxuGNL1gwzwomwR7sjwUt8WXYSuWcLYN6f9KpTZkP4k",
    "5GZSAgaVGQqegjhEkxpJjpSVLVmNnE2vx2PFLzr7kBBMKpGQ",
    "5E9fVY1jexCNVMjd2rdBsAxeamFGEMfzHcyTn2fHgdHeYc5p",
    "5FuzgvtfbZWdKSRxyYVPAPYNaNnf9cMnpT7phL3s2T3Kkrzo",
    "5FHxxe8ZKYaNmGcSLdG5ekxXeZDhQnk9cbpHdsJW8RunGpSs",
)

DEFAULT_MIDNIGHT_BLOCK_FILE = Path(__file__).with_name("midnight_blocks.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(message: str, *, level: str = "info") -> None:
    prefix = f"[{level}] " if level else ""
    print(f"{prefix}{message}", file=sys.stderr)


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
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"Failed to read JSON from {path}: {exc}", level="warn")
        return {}


def load_midnight_block_map(path: Path, network: str) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    if not payload:
        log(f"No midnight block cache found at {path}; live block search will be used.", level="info")
        return {}
    file_network = payload.get("network")
    if file_network and file_network != network:
        log(
            f"Midnight block cache {path} targets {file_network}; continuing with available entries.",
            level="warn",
        )
    blocks_raw = payload.get("blocks") or payload.get("block_map") or {}
    if not isinstance(blocks_raw, dict):
        log(f"Midnight cache {path} is missing a 'blocks' mapping.", level="warn")
        return {}
    blocks: dict[str, dict[str, Any]] = {}
    for key, entry in blocks_raw.items():
        try:
            if isinstance(entry, dict):
                block_val = int(entry.get("block"))
                ts_val = entry.get("block_timestamp_utc") or entry.get("timestamp_utc")
            else:
                block_val = int(entry)
                ts_val = None
        except (TypeError, ValueError):
            continue
        blocks[key] = {
            "block": block_val,
            "block_timestamp_utc": ts_val,
        }
    return blocks


def get_primary_subtensor(network: str) -> bt.Subtensor:
    try:
        return bt.Subtensor(network=network)
    except Exception as exc:
        raise SystemExit(f"Failed to connect to subtensor ({network}): {exc}") from exc


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


# ---------------------------------------------------------------------------
# Validator extraction
# ---------------------------------------------------------------------------
ValidatorEntry = Dict[str, Any]
ValidatorState = Dict[str, Dict[str, Any]]


def collect_netuid_matches(
    sub: bt.Subtensor,
    netuid: int,
    block: int,
    tracked_coldkeys: Set[str],
) -> Tuple[List[ValidatorEntry], ValidatorState]:
    try:
        neurons = sub.neurons_lite(netuid=netuid, block=block) or []
    except Exception as exc:
        log(
            f"neurons_lite failed for netuid {netuid} at block {block}: {type(exc).__name__} ({exc})",
            level="warn",
        )
        return [], {}

    entries: List[ValidatorEntry] = []
    placements: ValidatorState = {}
    for neuron in neurons:
        coldkey = getattr(neuron, "coldkey", None)
        if not isinstance(coldkey, str) or coldkey not in tracked_coldkeys:
            continue
        uid_raw = getattr(neuron, "uid", None)
        try:
            uid = int(uid_raw)
        except (TypeError, ValueError):
            uid = None
        hotkey = getattr(neuron, "hotkey", None)
        entry: ValidatorEntry = {"coldkey": coldkey}
        if isinstance(hotkey, str) and hotkey:
            entry["hotkey"] = hotkey
        if uid is not None:
            entry["uid"] = uid
        placements[coldkey] = {
            "netuid": netuid,
            "uid": uid,
            "hotkey": entry.get("hotkey"),
        }
        entries.append(entry)

    entries.sort(key=lambda item: item.get("uid", float("inf")))
    return entries, placements


def gather_all_netuids(sub: bt.Subtensor, block: int) -> List[int]:
    try:
        infos = sub.get_all_subnets_info(block=block) or []
    except Exception as exc:
        log(
            f"get_all_subnets_info failed at block {block}: {type(exc).__name__} ({exc}); falling back to default range.",
            level="warn",
        )
        infos = []
    netuids = sorted(
        {
            int(getattr(info, "netuid"))
            for info in infos
            if hasattr(info, "netuid") and getattr(info, "netuid") is not None
        }
    )
    if netuids:
        return netuids
    # Fallback: assume a reasonable subnet range (0-255).
    log("No netuids discovered; defaulting to range(0, 256).", level="warn")
    return list(range(0, 256))


def perform_full_scan(
    sub: bt.Subtensor,
    block: int,
    tracked_coldkeys: Set[str],
) -> Tuple[Dict[str, List[ValidatorEntry]], ValidatorState]:
    validators: Dict[str, List[ValidatorEntry]] = {}
    state: ValidatorState = {}
    netuids = gather_all_netuids(sub, block)
    for netuid in netuids:
        matches, placements = collect_netuid_matches(sub, netuid, block, tracked_coldkeys)
        if matches:
            validators[str(netuid)] = matches
        for coldkey, info in placements.items():
            state[coldkey] = info
    return validators, state


def gather_validators(
    sub: bt.Subtensor,
    block: int,
    tracked_coldkeys: Set[str],
) -> Tuple[Dict[str, List[ValidatorEntry]], ValidatorState, str]:
    validators, state = perform_full_scan(sub, block, tracked_coldkeys)
    return validators, state, "full"


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def build_payload(
    *,
    block: int,
    day: date,
    network: str,
    validators: Dict[str, List[ValidatorEntry]],
    tracked: List[str],
    timestamp: Optional[datetime],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "block": block,
        "date": day.strftime("%Y-%m-%d"),
        "network": network,
        "validators": {netuid: entries for netuid, entries in sorted(validators.items(), key=lambda item: int(item[0]))},
        "tracked_coldkeys": tracked,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if timestamp is not None:
        payload["block_timestamp_utc"] = timestamp.isoformat()
    return payload


def write_payload(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Wrote {path}", level="info")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache tracked validator placements at daily midnight blocks.",
    )
    parser.add_argument("--network", default="finney", help="Bittensor network or endpoint (default: finney)")
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--date", help="Single UTC day (YYYY-MM-DD)")
    date_group.add_argument(
        "--date-range",
        help="Inclusive UTC date range YYYY-MM-DD:YYYY-MM-DD",
    )
    parser.add_argument(
        "--midnight-blocks",
        default=str(DEFAULT_MIDNIGHT_BLOCK_FILE),
        help="Path to midnight block cache (default: ./midnight_blocks.json)",
    )
    parser.add_argument(
        "--coldkey",
        action="append",
        dest="coldkeys",
        help="Coldkey to track (repeat for multiple). Defaults to the built-in list when omitted.",
    )
    parser.add_argument(
        "--output",
        help="Destination JSON path (single-date mode only).",
    )
    parser.add_argument(
        "--output-dir",
        default="validator_cache",
        help="Directory for validators_<day>.json files (range mode default: validator_cache/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without writing files.",
    )
    return parser.parse_args()


def resolve_days(args: argparse.Namespace) -> List[date]:
    if args.date:
        return [parse_date(args.date)]
    start_str, end_str = args.date_range.split(":", maxsplit=1)
    start_day = parse_date(start_str)
    end_day = parse_date(end_str)
    if end_day < start_day:
        raise SystemExit("--date-range end must be on or after start")
    return list(daterange(start_day, end_day))


def resolve_block_for_day(
    day: date,
    *,
    sub: bt.Subtensor,
    midnight_blocks: dict[str, dict[str, Any]],
    previous_block: Optional[int],
) -> int:
    key = day.strftime("%Y-%m-%d")
    entry = midnight_blocks.get(key)
    if entry and isinstance(entry.get("block"), int):
        return int(entry["block"])
    target = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
    log(f"Finding midnight block for {key} via binary search...", level="info")
    min_block = previous_block if previous_block is not None else None
    return find_block_at_time(sub, target, min_block=min_block)


def main() -> None:
    args = parse_args()
    target_days = resolve_days(args)

    tracked_coldkeys = args.coldkeys if args.coldkeys else list(DEFAULT_COLDKEYS)
    tracked_set = {ck for ck in tracked_coldkeys if isinstance(ck, str)}
    if not tracked_set:
        raise SystemExit("No valid coldkeys were provided.")

    midnight_path = Path(args.midnight_blocks)
    if not midnight_path.is_absolute():
        midnight_path = Path(__file__).resolve().parent / midnight_path
    midnight_blocks = load_midnight_block_map(midnight_path, args.network)

    sub = get_primary_subtensor(args.network)

    previous_block: Optional[int] = None

    for day in target_days:
        block = resolve_block_for_day(
            day,
            sub=sub,
            midnight_blocks=midnight_blocks,
            previous_block=previous_block,
        )
        previous_block = block
        timestamp = get_block_timestamp(sub, block)

        validators, _, mode = gather_validators(sub, block, tracked_set)
        total_matches = sum(len(entries) for entries in validators.values())
        log(
            f"{day}: block {block} ({mode} scan) — {total_matches} tracked validators.",
            level="info",
        )
        payload = build_payload(
            block=block,
            day=day,
            network=args.network,
            validators=validators,
            tracked=tracked_coldkeys,
            timestamp=timestamp,
        )

        if args.dry_run:
            continue

        if args.date and len(target_days) == 1 and args.output:
            destination = Path(args.output)
            write_payload(destination, payload)
        elif args.date and len(target_days) == 1 and not args.output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            output_dir = Path(args.output_dir)
            filename = f"validators_{day.strftime('%Y-%m-%d')}.json"
            write_payload(output_dir / filename, payload)

    if args.dry_run:
        log("Dry run complete (no files written).", level="info")
    else:
        log("Validator cache generation finished.", level="info")


if __name__ == "__main__":
    main()
