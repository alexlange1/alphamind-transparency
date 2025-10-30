#!/usr/bin/env python3
"""
Precompute block numbers closest to 00:00 UTC for a range of dates.

The output JSON can be reused by other scripts (e.g. `dump_prices_at_block.py`)
to skip expensive binary searches when sampling daily snapshots.
"""

import argparse
import json
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

import bittensor as bt

from dump_prices_at_block import (
    AVERAGE_BLOCK_SECONDS,
    ESTIMATED_BLOCKS_PER_DAY,
    find_block_at_time,
    get_block_timestamp,
    log,
)

DEFAULT_START_DATE = date(2025, 2, 8)
MIDNIGHT_ALIGNMENT_TOLERANCE_SECONDS = 11


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}: {exc}") from exc


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    step = timedelta(days=1)
    while current <= end:
        yield current
        current += step


def load_existing_map(path: Path, network: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "network": network,
            "blocks": {},
        }

    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        log(f"Unable to read existing block map {path}: {exc}", level="warn")
        return {
            "network": network,
            "blocks": {},
        }

    existing_network = data.get("network")
    if existing_network and existing_network != network:
        log(
            f"Existing block map {path} was generated for network {existing_network}; reusing entries anyway.",
            level="warn",
        )

    raw_blocks = data.get("blocks") or data.get("block_map") or {}
    if not isinstance(raw_blocks, dict):
        raw_blocks = {}

    normalized: dict[str, dict[str, Any]] = {}
    for date_key, entry in raw_blocks.items():
        if isinstance(entry, dict):
            block_value = entry.get("block")
            timestamp_value = entry.get("block_timestamp_utc") or entry.get("timestamp_utc")
        else:
            block_value = entry
            timestamp_value = None
        try:
            block_int = int(block_value)
        except (TypeError, ValueError):
            continue
        normalized[date_key] = {
            "block": block_int,
            "block_timestamp_utc": timestamp_value,
        }

    data["network"] = network
    data["blocks"] = normalized
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", default="finney", help="Bittensor network (default: finney)")
    parser.add_argument(
        "--start-date",
        type=parse_date,
        default=DEFAULT_START_DATE,
        help="Earliest date in YYYY-MM-DD (default: 2025-02-08).",
    )
    parser.add_argument(
        "--end-date",
        type=parse_date,
        help="Last date in YYYY-MM-DD (default: today UTC).",
    )
    parser.add_argument(
        "--output",
        default="midnight_blocks.json",
        help="Destination JSON path (default: midnight_blocks.json alongside the script).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute every date even if it already exists in the output file.",
    )
    args = parser.parse_args()

    end_date = args.end_date or datetime.now(timezone.utc).date()
    if end_date < args.start_date:
        raise SystemExit("--end-date must not be earlier than --start-date")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent / output_path

    data = load_existing_map(output_path, args.network)
    blocks: dict[str, dict[str, Any]] = data.setdefault("blocks", {})

    sub = bt.Subtensor(network=args.network)

    recomputed = 0
    skipped = 0
    prev_block: int | None = None
    prev_block_time: datetime | None = None

    for current_date in iter_dates(args.start_date, end_date):
        date_str = current_date.isoformat()
        if not args.overwrite and date_str in blocks:
            skipped += 1
            entry = blocks[date_str]
            try:
                prev_block = int(entry.get("block"))  # type: ignore[arg-type]
            except Exception:
                prev_block = None
            ts_value = entry.get("block_timestamp_utc") if isinstance(entry, dict) else None
            try:
                prev_block_time = datetime.fromisoformat(ts_value) if ts_value else None  # type: ignore[arg-type]
            except Exception:
                prev_block_time = None
            continue

        target_dt = datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc)
        log(f"Locating midnight block for {date_str}...", level="info")

        block: int | None = None
        block_time: datetime | None = None

        if prev_block is not None:
            estimated = max(1, prev_block + ESTIMATED_BLOCKS_PER_DAY)
            log(f"  Starting from estimated block {estimated} based on previous day.", level="info")
            attempt_block = estimated
            for attempt in range(6):
                block_time = get_block_timestamp(sub, attempt_block)
                if block_time is None:
                    log(f"  Timestamp unavailable at block {attempt_block}; aborting shortcuts.", level="warn")
                    break

                diff_seconds = (block_time - target_dt).total_seconds()
                log(
                    f"  Attempt {attempt + 1}: block {attempt_block} is {diff_seconds:+.1f}s from midnight.",
                    level="info",
                )
                if abs(diff_seconds) <= MIDNIGHT_ALIGNMENT_TOLERANCE_SECONDS:
                    block = attempt_block
                    log(
                        f"  Accepted block {block} within ±{MIDNIGHT_ALIGNMENT_TOLERANCE_SECONDS}s of midnight.",
                        level="info",
                    )
                    break

                adjustment = int(round(diff_seconds / AVERAGE_BLOCK_SECONDS))
                if adjustment == 0:
                    adjustment = 1 if diff_seconds > 0 else -1
                attempt_block = max(1, attempt_block - adjustment)
            else:
                log("  Shortcut iterations exhausted; falling back to binary search.", level="warn")

        if block is None:
            try:
                block = find_block_at_time(sub, target_dt)
            except Exception as exc:
                raise RuntimeError(f"Binary search failed for {date_str}: {exc}") from exc
            block_time = get_block_timestamp(sub, block)

        blocks[date_str] = {
            "block": int(block),
            "block_timestamp_utc": block_time.isoformat() if isinstance(block_time, datetime) else None,
        }
        recomputed += 1
        prev_block = int(block)
        prev_block_time = block_time if isinstance(block_time, datetime) else None

    data["network"] = args.network
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data["start_date"] = args.start_date.isoformat()
    data["end_date"] = end_date.isoformat()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    log(
        f"Saved midnight block map to {output_path} "
        f"(updated {recomputed} date(s), skipped {skipped}).",
        level="info",
    )


if __name__ == "__main__":
    main()
