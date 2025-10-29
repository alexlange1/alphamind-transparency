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
from typing import Any, Sequence

import bittensor as bt
from async_substrate_interface.errors import SubstrateRequestException


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
DEFAULT_VALIDATOR_COLDKEYS: tuple[str, ...] = (
    "5GZSAgaVGQqegjhEkxpJjpSVLVmNnE2vx2PFLzr7kBBMKpGQ",
    "5HBtpwxuGNL1gwzwomwR7sjwUt8WXYSuWcLYN6f9KpTZkP4k",
    "5FuzgvtfbZWdKSRxyYVPAPYNaNnf9cMnpT7phL3s2T3Kkrzo",
)
DEFAULT_VALIDATOR_NETUIDS: tuple[int, ...] = ()


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


def neuron_is_validator(neuron: Any) -> bool:
    """Return True if the neuron is a validator across different SDK versions."""
    for attr in ("is_validator", "validator_permit", "validator_permits"):
        value = getattr(neuron, attr, None)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            uid = getattr(neuron, "uid", None)
            if uid is None:
                continue
            idx = int(uid)
            if 0 <= idx < len(value):
                return bool(value[idx])
            continue
        if callable(value):
            try:
                value = value()
            except TypeError:
                pass
        return bool(value)
    return False


def list_subnet_validators(sub: bt.Subtensor, netuid: int, block: int) -> list[dict[str, Any]]:
    """Return validator identity rows for the requested subnet."""
    try:
        neurons = sub.neurons_lite(netuid=netuid, block=block) or []
    except AttributeError as exc:  # pragma: no cover - version specific
        raise RuntimeError(
            "Installed bittensor version does not expose `neurons_lite`. "
            "Upgrade bittensor or adjust the script to use a compatible API."
        ) from exc

    validators: list[dict[str, Any]] = []
    for neuron in neurons:
        if not neuron_is_validator(neuron):
            continue
        uid = getattr(neuron, "uid", None)
        if uid is None:
            continue
        validators.append(
            {
                "uid": int(uid),
                "hotkey": getattr(neuron, "hotkey", None),
                "coldkey": getattr(neuron, "coldkey", None),
            }
        )

    validators.sort(key=lambda row: row["uid"])
    return validators


def find_validators_until_coldkeys(
    sub: bt.Subtensor,
    netuid: int,
    start_block: int,
    coldkeys: Sequence[str] | None = None,
    max_backtrack: int | None = 0,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Search backward from start_block until validators with selected coldkeys are found.

    Returns (block_used, all_validators, matched_validators). When `coldkeys` is falsy,
    the embedded DEFAULT_VALIDATOR_COLDKEYS are used as the search target.
    """
    if start_block <= 0:
        raise SystemExit("--block must be a positive integer")

    effective_coldkeys = coldkeys if coldkeys else DEFAULT_VALIDATOR_COLDKEYS
    coldkey_set = {ck for ck in effective_coldkeys if ck}
    backtracked = 0
    block = start_block

    while block > 0:
        validators = list_subnet_validators(sub, netuid, block)
        matches = (
            validators
            if not coldkey_set
            else [row for row in validators if row.get("coldkey") in coldkey_set]
        )
        if matches:
            return block, validators, matches

        backtracked += 1
        if max_backtrack is not None and backtracked > max_backtrack:
            break
        block -= 1

    coldkey_list = ", ".join(sorted(coldkey_set)) or "unknown"
    raise RuntimeError(
        f"No validators with coldkeys [{coldkey_list}] found within the search window (start {start_block}, backtracked {backtracked} blocks)."
    )


def resolve_validator_matches(
    sub: bt.Subtensor,
    netuid: int,
    target_block: int,
    coldkeys: Sequence[str] | None,
    validator_cache: dict[int, dict[str, dict[str, Any]]] | None,
    max_backtrack: int | None,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (block_used, all_validators, matched subset) for a subnet."""
    target_coldkeys = [ck for ck in (coldkeys or DEFAULT_VALIDATOR_COLDKEYS) if ck]
    if not target_coldkeys:
        validators = list_subnet_validators(sub, netuid, target_block)
        return target_block, validators, []

    cache_for_net = None
    if validator_cache is not None:
        cache_for_net = validator_cache.setdefault(netuid, {})

    validators: list[dict[str, Any]] | None = None
    if cache_for_net:
        validators = list_subnet_validators(sub, netuid, target_block)
        by_uid = {row["uid"]: row for row in validators}
        by_coldkey = {
            row.get("coldkey"): row for row in validators if row.get("coldkey")
        }
        matches: list[dict[str, Any]] = []
        missing: list[str] = []
        for coldkey in target_coldkeys:
            cached_entry = cache_for_net.get(coldkey)
            row = None
            if cached_entry is not None:
                row = by_uid.get(int(cached_entry["uid"]))
                if row and row.get("coldkey") != coldkey:
                    row = None
            if row is None:
                row = by_coldkey.get(coldkey)
            if row:
                matches.append(row)
                cache_for_net[coldkey] = row
            else:
                missing.append(coldkey)
        if not missing:
            return target_block, validators, matches

    block_used, validators, matches = find_validators_until_coldkeys(
        sub,
        netuid,
        target_block,
        coldkeys=target_coldkeys,
        max_backtrack=max_backtrack,
    )
    if cache_for_net is not None:
        for row in matches:
            coldkey = row.get("coldkey")
            if coldkey:
                cache_for_net[coldkey] = row
    return block_used, validators, matches


def log(message: str, *, level: str = "info") -> None:
    prefix = f"[{level}] " if level else ""
    print(f"{prefix}{message}", file=sys.stderr)


def fetch_prices_at_block(
    sub: bt.Subtensor,
    block: int,
    *,
    validator_targets: set[int] | None = None,
    validator_coldkeys: Sequence[str] | None = None,
    validator_cache: dict[int, dict[str, dict[str, Any]]] | None = None,
    validator_max_backtrack: int | None = 0,
    include_all_validators: bool = False,
):
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
    tracking_all = validator_targets is None

    rows = []
    for info in infos:
        netuid = int(getattr(info, "netuid"))
        price_tao = price_map.get(netuid)

        row: dict[str, Any] = {
            "netuid": netuid,
            #"symbol": getattr(info, "symbol", None),
            #"name": getattr(info, "subnet_name", None),
            "price_tao_per_alpha": price_tao,
        }
        tracked = tracking_all or (validator_targets is not None and netuid in validator_targets)
        validator_meta: dict[str, Any] | None = None
        if include_all_validators:
            try:
                validator_block, validators_list, matches = resolve_validator_matches(
                    sub,
                    netuid,
                    block,
                    validator_coldkeys,
                    validator_cache,
                    validator_max_backtrack,
                )
            except RuntimeError as exc:
                log(f"Validator lookup failed for netuid {netuid}: {exc}", level="warn")
                validator_block = block
                validators_list = list_subnet_validators(sub, netuid, block)
                matches = []
            validator_meta = {
                "block": validator_block,
                "entries": validators_list,
            }
            if matches:
                validator_meta["matched_coldkeys"] = matches
        elif tracked:
            try:
                validator_block, _, matches = resolve_validator_matches(
                    sub,
                    netuid,
                    block,
                    validator_coldkeys,
                    validator_cache,
                    validator_max_backtrack,
                )
            except RuntimeError as exc:
                log(f"Validator lookup failed for netuid {netuid}: {exc}", level="warn")
                validator_block = block
                matches = []
            validator_meta = {
                "block": validator_block,
                "matched_coldkeys": matches,
            }

        if validator_meta:
            row["validators"] = validator_meta

        rows.append(row)

    # include any subnets from fallback price map that might not be present in infos
    known_netuid = {row["netuid"] for row in rows}
    for netuid, price in price_map.items():
        if netuid in known_netuid:
            continue
        rows.append({
            "netuid": netuid,
            "price_tao_per_alpha": price,
        })

    if validator_targets:
        for netuid in validator_targets:
            if netuid in known_netuid:
                continue
            try:
                validator_block, validators_list, matches = resolve_validator_matches(
                    sub,
                    netuid,
                    block,
                    validator_coldkeys,
                    validator_cache,
                    validator_max_backtrack,
                )
            except RuntimeError:
                matches = []
                validator_block = block
                validators_list = []
            row: dict[str, Any] = {
                "netuid": netuid,
                "price_tao_per_alpha": None,
            }
            meta: dict[str, Any] = {"block": validator_block}
            if include_all_validators:
                meta["entries"] = validators_list
            meta["matched_coldkeys"] = matches
            row["validators"] = meta
            rows.append(row)
            known_netuid.add(netuid)

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
    parser.add_argument(
        "--output",
        help="Write JSON to this path instead of stdout (single-date mode only).",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for auto-named JSON output (default: outputs in date-range mode).",
    )
    parser.add_argument(
        "--validator-coldkey",
        action="append",
        help="Extra validator coldkey(s) to track alongside the defaults.",
    )
    parser.add_argument(
        "--no-default-validator-coldkeys",
        action="store_true",
        help="Ignore the embedded default validator coldkeys.",
    )
    parser.add_argument(
        "--validator-netuid",
        action="append",
        type=int,
        help="Subnet(s) to attach validator metadata (default: all subnets).",
    )
    parser.add_argument(
        "--validator-max-backtrack",
        type=int,
        default=0,
        help="Blocks to search backward when validator state is pruned (default: 0, use -1 for unlimited).",
    )
    parser.add_argument(
        "--no-validator-info",
        action="store_true",
        help="Skip validator lookups entirely.",
    )
    parser.add_argument(
        "--include-all-validators",
        action="store_true",
        help="Attach full validator lists for every subnet (default: only matched coldkeys).",
    )
    args = parser.parse_args()

    sub = bt.Subtensor(network=args.network)

    include_validators = not args.no_validator_info
    include_all_validators = args.include_all_validators
    validator_coldkeys: list[str] | None = None
    validator_targets: set[int] | None = None
    validator_max_backtrack: int | None = None
    validator_cache: dict[int, dict[str, dict[str, Any]]] | None = None

    if include_validators:
        coldkey_candidates: list[str] = []
        if not args.no_default_validator_coldkeys:
            coldkey_candidates.extend(DEFAULT_VALIDATOR_COLDKEYS)
        coldkey_candidates.extend(args.validator_coldkey or [])
        seen_ck: set[str] = set()
        validator_coldkeys = []
        for ck in coldkey_candidates:
            if not ck or ck in seen_ck:
                continue
            seen_ck.add(ck)
            validator_coldkeys.append(ck)

        if not validator_coldkeys:
            include_validators = False
        else:
            if args.validator_netuid:
                validator_targets = {net for net in args.validator_netuid if net is not None}
                for net in list(validator_targets):
                    if net < 0:
                        raise SystemExit("--validator-netuid values must be non-negative")
            else:
                validator_targets = None  # track all subnets

            validator_max_backtrack = (
                None
                if args.validator_max_backtrack is not None and args.validator_max_backtrack < 0
                else args.validator_max_backtrack
            )
            validator_cache = {}

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

        prev_block: int | None = None
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            requested_dt = parse_requested_datetime(date_str, args.time)
            target_utc = requested_dt.astimezone(timezone.utc)

            min_block = prev_block
            max_block = prev_block + ESTIMATED_BLOCKS_PER_DAY * 2 if prev_block else None

            log(f"Finding block closest to {target_utc.isoformat()} UTC for {date_str}...")
            block = find_block_at_time(sub, target_utc, min_block=min_block, max_block=max_block)
            block_time = get_block_timestamp(sub, block)

            if block_time is None:
                raise RuntimeError(f"Unable to read timestamp for block {block}")

            if max_block is not None and block_time < target_utc:
                block = find_block_at_time(sub, target_utc)
                block_time = get_block_timestamp(sub, block)
                if block_time is None:
                    raise RuntimeError(f"Unable to read timestamp for block {block}")

            rows = fetch_prices_at_block(
                sub,
                block,
                validator_targets=validator_targets if include_validators else None,
                validator_coldkeys=validator_coldkeys,
                validator_cache=validator_cache,
                validator_max_backtrack=validator_max_backtrack,
                include_all_validators=include_all_validators if include_validators else False,
            )
            output = {
                "requested_time": requested_dt.isoformat(),
                "closest_block": block,
                "block_timestamp_utc": block_time.isoformat(),
                "network": args.network,
                "prices": rows,
            }

            out_path = output_dir / f"prices_{date_str}.json"
            out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"Saved {out_path} (block {block} at {block_time.isoformat()} UTC)")

            prev_block = block
            current_date += timedelta(days=1)
    else:
        requested_dt = parse_requested_datetime(args.date, args.time)
        target_utc = requested_dt.astimezone(timezone.utc)

        log(f"Finding block closest to {target_utc.isoformat()} UTC...")
        block = find_block_at_time(sub, target_utc)
        block_time = get_block_timestamp(sub, block)
        if block_time is None:
            raise RuntimeError(f"Unable to read timestamp for block {block}")
        log(f"Closest block: {block} at {block_time.isoformat()} UTC")

        rows = fetch_prices_at_block(
            sub,
            block,
            validator_targets=validator_targets if include_validators else None,
            validator_coldkeys=validator_coldkeys,
            validator_cache=validator_cache,
            validator_max_backtrack=validator_max_backtrack,
            include_all_validators=include_all_validators if include_validators else False,
        )
        output = {
            "requested_time": requested_dt.isoformat(),
            "closest_block": block,
            "block_timestamp_utc": block_time.isoformat(),
            "network": args.network,
            "prices": rows,
        }

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"Saved {out_path} (block {block} at {block_time.isoformat()} UTC)")
        elif args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"prices_{requested_dt.date().isoformat()}.json"
            out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"Saved {out_path} (block {block} at {block_time.isoformat()} UTC)")
        else:
            print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
