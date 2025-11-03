#!/usr/bin/env python3
"""
Cache per-block dividend ratios for tracked validators.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import local
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
DEFAULT_VALIDATOR_CACHE = Path("validator_cache")

_THREAD_STATE = local()


# ---------------------------------------------------------------------------
# Utilities
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
        log(f"No midnight block cache found at {path}; live search will be used.", level="info")
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


def get_worker_subtensor(network: str, primary: bt.Subtensor) -> bt.Subtensor:
    if getattr(_THREAD_STATE, "subtensor", None) is None:
        try:
            _THREAD_STATE.subtensor = bt.Subtensor(network=network)
        except Exception as exc:
            log(f"Worker subtensor init failed ({exc}); reusing primary connection.", level="warn")
            _THREAD_STATE.subtensor = primary
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


def balance_to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    for attr in ("tao", "rao", "float_value"):
        if hasattr(value, attr):
            val = getattr(value, attr)
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Validator cache handling
# ---------------------------------------------------------------------------
ValidatorCache = Dict[int, List[Dict[str, Any]]]


def load_validator_cache_for_day(
    cache_dir: Path,
    day: date,
    tracked_coldkeys: Set[str],
) -> Tuple[ValidatorCache, Set[str]]:
    path = cache_dir / f"validators_{day.strftime('%Y-%m-%d')}.json"
    data = load_json(path)
    if not data:
        log(f"No validator cache found for {day} at {path}", level="warn")
        return {}, set()

    validators_obj = data.get("validators")
    if not isinstance(validators_obj, dict):
        log(f"Validator cache {path} missing 'validators' object.", level="warn")
        return {}, set()

    netuid_map: ValidatorCache = {}
    cached_coldkeys: Set[str] = set()
    for netuid_str, entries in validators_obj.items():
        try:
            netuid = int(netuid_str)
        except (TypeError, ValueError):
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            coldkey = entry.get("coldkey")
            if coldkey not in tracked_coldkeys:
                continue
            sanitized = {
                "coldkey": coldkey,
                "uid": entry.get("uid"),
                "hotkey": entry.get("hotkey"),
            }
            netuid_map.setdefault(netuid, []).append(sanitized)
            cached_coldkeys.add(coldkey)
    return netuid_map, cached_coldkeys


# ---------------------------------------------------------------------------
# Neuron sampling
# ---------------------------------------------------------------------------
def fetch_neuron_metrics(
    sub: bt.Subtensor,
    netuid: int,
    block: int,
) -> Tuple[Optional[Dict[int, Dict[str, Any]]], Optional[str]]:
    try:
        neurons = sub.neurons_lite(netuid=netuid, block=block) or []
    except Exception as exc:
        message = f"neurons_lite failed for netuid {netuid} at block {block}: {type(exc).__name__} ({exc})"
        log(message, level="warn")
        return None, message

    metrics: Dict[int, Dict[str, Any]] = {}
    for neuron in neurons:
        uid_raw = getattr(neuron, "uid", None)
        try:
            uid = int(uid_raw)
        except (TypeError, ValueError):
            continue
        metrics[uid] = {
            "coldkey": getattr(neuron, "coldkey", None),
            "hotkey": getattr(neuron, "hotkey", None),
            "stake": balance_to_float(getattr(neuron, "stake", 0)),
            "dividends": balance_to_float(getattr(neuron, "dividends", 0)),
        }
    return metrics, None


def compute_payout_ratio(dividends: float, stake: float) -> Optional[float]:
    if stake <= 0:
        return None
    ratio = dividends / stake
    if math.isfinite(ratio):
        return ratio
    return None


def collect_block_sample(
    block: int,
    *,
    network: str,
    primary_sub: bt.Subtensor,
    validator_map: ValidatorCache,
    tracked_coldkeys: List[str],
    cached_coldkeys: Set[str],
) -> Dict[str, Any]:
    sub = get_worker_subtensor(network, primary_sub)
    timestamp = get_block_timestamp(sub, block)

    netuids = sorted(validator_map.keys())
    metrics_by_netuid: Dict[int, Dict[int, Dict[str, Any]]] = {}
    errors_by_netuid: Dict[int, str] = {}
    for netuid in netuids:
        metrics, error = fetch_neuron_metrics(sub, netuid, block)
        if metrics is not None:
            metrics_by_netuid[netuid] = metrics
        if error:
            errors_by_netuid[netuid] = error

    netuid_results: Dict[str, List[Dict[str, Any]]] = {}

    for netuid in netuids:
        entries = validator_map.get(netuid, [])
        metrics_for_netuid = metrics_by_netuid.get(netuid)
        error = errors_by_netuid.get(netuid)
        results: List[Dict[str, Any]] = []
        for entry in entries:
            coldkey = entry.get("coldkey")
            result: Dict[str, Any] = {"coldkey": coldkey}
            expected_uid = entry.get("uid")
            if isinstance(expected_uid, int):
                result["uid"] = expected_uid
            expected_hotkey = entry.get("hotkey")
            if isinstance(expected_hotkey, str) and expected_hotkey:
                result["expected_hotkey"] = expected_hotkey

            if error:
                result["status"] = "error"
                result["error"] = error
                results.append(result)
                continue

            if metrics_for_netuid is None:
                result["status"] = "missing_metrics"
                results.append(result)
                continue

            match_uid = None
            neuron = None
            if isinstance(expected_uid, int) and expected_uid in metrics_for_netuid:
                match_uid = expected_uid
                neuron = metrics_for_netuid[expected_uid]
            else:
                for uid, data in metrics_for_netuid.items():
                    if data.get("coldkey") == coldkey:
                        match_uid = uid
                        neuron = data
                        result.setdefault("uid", uid)
                        break

            if neuron is None:
                result["status"] = "not_found"
                results.append(result)
                continue

            observed_coldkey = neuron.get("coldkey")
            if observed_coldkey is not None:
                result["observed_coldkey"] = observed_coldkey
            observed_hotkey = neuron.get("hotkey")
            if observed_hotkey:
                result["observed_hotkey"] = observed_hotkey

            if observed_coldkey != coldkey:
                result["status"] = "coldkey_mismatch"
                results.append(result)
                continue

            dividends = float(neuron.get("dividends", 0.0) or 0.0)
            stake = float(neuron.get("stake", 0.0) or 0.0)
            ratio = compute_payout_ratio(dividends, stake)
            result.update(
                {
                    "status": "ok",
                    "stake": stake,
                    "dividends": dividends,
                    "payout_ratio": ratio,
                    "payout_ratio_nanos": int(round(ratio * 1_000_000_000)) if ratio is not None else None,
                }
            )
            results.append(result)

        if results:
            netuid_results[str(netuid)] = results

    uncached = sorted(set(tracked_coldkeys) - cached_coldkeys)

    sample: Dict[str, Any] = {
        "block": block,
        "netuids": netuid_results,
        "uncached_coldkeys": uncached,
    }
    if timestamp is not None:
        sample["block_timestamp_utc"] = timestamp.isoformat()
    return sample


def collect_day_samples(
    blocks: List[int],
    *,
    network: str,
    primary_sub: bt.Subtensor,
    validator_map: ValidatorCache,
    tracked_coldkeys: List[str],
    cached_coldkeys: Set[str],
    workers: int,
) -> List[Dict[str, Any]]:
    if not blocks:
        return []

    samples: List[Dict[str, Any]] = []
    if workers <= 1:
        for block in blocks:
            samples.append(
                collect_block_sample(
                    block,
                    network=network,
                    primary_sub=primary_sub,
                    validator_map=validator_map,
                    tracked_coldkeys=tracked_coldkeys,
                    cached_coldkeys=cached_coldkeys,
                )
            )
    else:
        max_workers = max(1, workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_block = {
                executor.submit(
                    collect_block_sample,
                    block,
                    network=network,
                    primary_sub=primary_sub,
                    validator_map=validator_map,
                    tracked_coldkeys=tracked_coldkeys,
                    cached_coldkeys=cached_coldkeys,
                ): block
                for block in blocks
            }
            for future in as_completed(future_to_block):
                block = future_to_block[future]
                try:
                    sample = future.result()
                    samples.append(sample)
                except Exception as exc:
                    log(f"Block {block} failed: {exc}", level="warn")
    samples.sort(key=lambda item: item["block"])
    return samples


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def build_daily_payload(
    *,
    day: date,
    network: str,
    config: Dict[str, Any],
    tracked_coldkeys: List[str],
    samples: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "date": day.strftime("%Y-%m-%d"),
        "network": network,
        "config": config,
        "tracked_coldkeys": tracked_coldkeys,
        "samples": samples,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_payload(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Wrote {path}", level="info")


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache per-block dividend ratios for tracked validators.",
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
        "--validator-cache",
        default=str(DEFAULT_VALIDATOR_CACHE),
        help="Directory containing validators_<day>.json files (default: validator_cache)",
    )
    parser.add_argument(
        "--coldkey",
        action="append",
        dest="coldkeys",
        help="Coldkey to track (repeat for multiple). Defaults to built-in list when omitted.",
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
        "--workers",
        type=int,
        default=4,
        help="Concurrent block fetchers (default: 4).",
    )
    parser.add_argument(
        "--output",
        help="Destination JSON path (single-date mode only).",
    )
    parser.add_argument(
        "--output-dir",
        default="dividend_cache",
        help="Directory for dividends_<day>.json files (range mode default: dividend_cache/).",
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    if args.block_step < 1:
        raise SystemExit("--block-step must be >= 1")
    if args.block_offset < 0:
        raise SystemExit("--block-offset must be >= 0")

    tracked_coldkeys = args.coldkeys if args.coldkeys else list(DEFAULT_COLDKEYS)
    tracked_coldkeys = [ck for ck in tracked_coldkeys if isinstance(ck, str)]
    if not tracked_coldkeys:
        raise SystemExit("No valid coldkeys provided.")
    tracked_set = set(tracked_coldkeys)

    target_days = resolve_days(args)

    midnight_path = Path(args.midnight_blocks)
    if not midnight_path.is_absolute():
        midnight_path = Path(__file__).resolve().parent / midnight_path
    midnight_blocks = load_midnight_block_map(midnight_path, args.network)

    validator_cache_dir = Path(args.validator_cache)
    primary_sub = get_primary_subtensor(args.network)

    previous_block: Optional[int] = None
    for day in target_days:
        block = resolve_block_for_day(
            day,
            sub=primary_sub,
            midnight_blocks=midnight_blocks,
            previous_block=previous_block,
        )
        previous_block = block

        validator_map, cached_coldkeys = load_validator_cache_for_day(validator_cache_dir, day, tracked_set)
        if not cached_coldkeys:
            log(
                f"No cached validators found for {day}; tracked coldkeys will appear under 'uncached_coldkeys'.",
                level="warn",
            )

        next_day = day + timedelta(days=1)
        next_day_key = next_day.strftime("%Y-%m-%d")
        next_entry = midnight_blocks.get(next_day_key)
        if next_entry and isinstance(next_entry.get("block"), int):
            next_block = int(next_entry["block"])
        else:
            target_dt = datetime.combine(next_day, datetime.min.time()).replace(tzinfo=timezone.utc)
            log(f"Finding midnight block for {next_day_key} via binary search...", level="info")
            next_block = find_block_at_time(primary_sub, target_dt, min_block=block)
        # Trim block list to [effective_start, next_block)
        effective_start = block + args.block_offset
        if effective_start >= next_block:
            log(
                f"Offset skips entire range for {day}: start {block}, offset {args.block_offset}, next {next_block}.",
                level="warn",
            )
            samples = []
        else:
            trimmed_blocks = list(range(effective_start, next_block, args.block_step))
            log(
                f"{day}: sampling {len(trimmed_blocks)} blocks [{effective_start}, {next_block}) step {args.block_step}",
                level="info",
            )
            samples = collect_day_samples(
                trimmed_blocks,
                network=args.network,
                primary_sub=primary_sub,
                validator_map=validator_map,
                tracked_coldkeys=tracked_coldkeys,
                cached_coldkeys=cached_coldkeys,
                workers=args.workers,
            )

        payload = build_daily_payload(
            day=day,
            network=args.network,
            config={
                "block_step": args.block_step,
                "block_offset": args.block_offset,
                "workers": args.workers,
            },
            tracked_coldkeys=tracked_coldkeys,
            samples=samples,
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
            filename = f"dividends_{day.strftime('%Y-%m-%d')}.json"
            write_payload(output_dir / filename, payload)

    if args.dry_run:
        log("Dry run complete (no files written).", level="info")
    else:
        log("Dividend ratio cache generation finished.", level="info")


if __name__ == "__main__":
    main()
