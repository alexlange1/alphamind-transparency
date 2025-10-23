#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class SalvageResult:
    payload: Dict[str, Any]
    skipped_reason: Optional[str] = None


def find_json_payload(text: str) -> Optional[str]:
    """Return the first JSON object embedded in the text, if any."""
    start = text.find("{")
    if start == -1:
        return None
    return text[start:]


def load_price_snapshot(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        raw_text = path.read_text()
    except OSError as exc:
        return None, f"failed to read file: {exc}"

    json_payload = find_json_payload(raw_text)
    if json_payload is None:
        return None, "no JSON object found"

    try:
        data = json.loads(json_payload)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"

    if not isinstance(data, dict):
        return None, "top-level JSON is not an object"
    return data, None


def extract_prices(prices: Iterable[Any]) -> Tuple[Dict[int, float], bool, bool]:
    sanitized: Dict[int, float] = {}
    found_numeric = False
    found_nonzero = False

    for entry in prices:
        if not isinstance(entry, dict):
            continue
        netuid = entry.get("netuid")
        price = entry.get("price_tao_per_alpha")
        if not isinstance(netuid, int):
            continue
        if isinstance(price, (int, float)):
            found_numeric = True
            if netuid == 0:
                continue
            sanitized[netuid] = float(price)
            found_nonzero = True
    return sanitized, found_numeric, found_nonzero


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def build_output(
    source_path: Path,
    raw: Dict[str, Any],
    prices: Dict[int, float],
) -> Dict[str, Any]:
    by_netuid = OrderedDict(
        (str(netuid), value) for netuid, value in sorted(prices.items())
    )
    values = list(prices.values())

    total = sum(values)
    active = len(values)
    minimum = min(values) if values else None
    maximum = max(values) if values else None
    average = total / active if active else None

    timestamp = raw.get("block_timestamp_utc")
    parsed_timestamp: Optional[str] = None
    if isinstance(timestamp, str):
        parsed_timestamp = timestamp

    date_token = source_path.stem.replace("-", "")
    metadata: Dict[str, Any] = {
        "collection_method": "btsdk scripts v2",
        "date": date_token if date_token else None,
        "network": raw.get("network"),
        "timestamp": parsed_timestamp,
        "closest_block": raw.get("closest_block"),
        "requested_local_time": raw.get("requested_local_noon"),
        "total_active_subnets": active,
        "total_emission_rate": total,
    }

    statistics = {
        "active_subnets": active,
        "avg_emission_rate": average,
        "max_emission_rate": maximum,
        "min_emission_rate": minimum,
        "total_emission_rate": total,
    }

    generated = {
        "emissions": by_netuid,
        "metadata": metadata,
        "statistics": statistics,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return generated


def salvage_file(path: Path) -> SalvageResult:
    raw, error = load_price_snapshot(path)
    if error:
        return SalvageResult(payload={}, skipped_reason=error)

    prices_field = raw.get("prices")
    if not isinstance(prices_field, list):
        return SalvageResult(payload={}, skipped_reason="missing 'prices' list")

    prices, found_numeric, found_nonzero = extract_prices(prices_field)
    if not found_numeric:
        return SalvageResult(payload={}, skipped_reason="no numeric price records")
    if not found_nonzero:
        return SalvageResult(payload={}, skipped_reason="only netuid 0 has numeric price")

    requested_dt = parse_iso_datetime(raw.get("requested_local_noon"))
    block_dt = parse_iso_datetime(raw.get("block_timestamp_utc"))
    if requested_dt and block_dt and requested_dt.date() != block_dt.date():
        return SalvageResult(
            payload={},
            skipped_reason="requested local time date differs from block timestamp date",
        )

    output = build_output(path, raw, prices)
    return SalvageResult(payload=output)


def write_output(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def run(input_dir: Path, output_dir: Path, dry_run: bool) -> None:
    processed = 0
    skipped: List[Tuple[Path, str]] = []

    for source_path in sorted(input_dir.glob("*.json")):
        result = salvage_file(source_path)
        if result.skipped_reason:
            skipped.append((source_path, result.skipped_reason))
            continue

        processed += 1
        if dry_run:
            continue

        date_token = source_path.stem.replace("-", "")
        destination_name = f"emissions_v2_{date_token}.json" if date_token else source_path.name
        destination = output_dir / destination_name
        write_output(destination, result.payload)

    print(f"Processed {processed} file(s).")
    if not dry_run:
        print(f"Output written to: {output_dir}")

    if skipped:
        print("Skipped files:")
        for source_path, reason in skipped:
            print(f"  - {source_path}: {reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Salvage price data from JSON snapshots and convert to model format.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("jsons"),
        help="Directory containing raw JSON snapshots (default: jsons)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("jsons_salvaged"),
        help="Directory for converted JSON files (default: jsons_salvaged)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and report skipped items without writing output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.input, args.output, args.dry_run)


if __name__ == "__main__":
    main()
