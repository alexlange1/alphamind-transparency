#!/usr/bin/env python3
"""
Translate multi-sample price dumps into the multi-sample emissions format.

Usage:
    python scripts/translate_price_dumps.py --input scripts/multi-24 --output translated
"""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

COLLECTION_METHOD = "btsdk scripts v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert price dump JSON files into emissions_v2 outputs with multi-sample support.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input JSON file or directory containing price dump JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("translated"),
        help="Directory where translated emissions files will be written (default: translated).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse inputs and report outcomes without writing files.",
    )
    return parser.parse_args()


def iter_input_paths(target: Path) -> Iterable[Path]:
    if target.is_file():
        yield target
        return

    if not target.exists():
        return

    if target.is_dir():
        for path in sorted(target.glob("*.json")):
            if path.is_file():
                yield path


def load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        text = path.read_text()
    except OSError as exc:
        return None, f"failed to read file: {exc}"

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"

    if not isinstance(data, dict):
        return None, "top-level JSON is not an object"
    return data, None


def coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def sanitize_emissions(prices: Iterable[Any]) -> OrderedDict[str, float]:
    sanitized: Dict[int, float] = {}

    for entry in prices:
        if not isinstance(entry, dict):
            continue

        netuid = entry.get("netuid")
        price_raw = entry.get("price_tao_per_alpha")
        if not isinstance(netuid, int) or netuid == 0:
            continue

        price = coerce_float(price_raw)
        if price is None:
            continue

        sanitized[netuid] = price

    ordered = OrderedDict((str(netuid), sanitized[netuid]) for netuid in sorted(sanitized))
    return ordered


def compute_statistics(emission_values: List[float]) -> Dict[str, Optional[float]]:
    if not emission_values:
        return {
            "active_subnets": 0,
            "avg_emission_rate": None,
            "max_emission_rate": None,
            "min_emission_rate": None,
            "total_emission_rate": 0.0,
        }

    total = float(sum(emission_values))
    active = len(emission_values)
    minimum = min(emission_values)
    maximum = max(emission_values)
    average = total / active if active else None

    return {
        "active_subnets": active,
        "avg_emission_rate": average,
        "max_emission_rate": maximum,
        "min_emission_rate": minimum,
        "total_emission_rate": total,
    }


def derive_date_token(source_path: Path, payload: Dict[str, Any]) -> str:
    raw_date = payload.get("date")
    if isinstance(raw_date, str):
        digits = "".join(ch for ch in raw_date if ch.isdigit())
        if len(digits) == 8:
            return digits

    stem_digits = "".join(ch for ch in source_path.stem if ch.isdigit())
    if len(stem_digits) >= 8:
        return stem_digits[-8:]

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return today


def derive_samples(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    samples_raw = payload.get("samples")
    if isinstance(samples_raw, list) and samples_raw:
        return [sample for sample in samples_raw if isinstance(sample, dict)]

    # Legacy single-sample layout: treat top-level object as the only sample.
    if isinstance(payload.get("prices"), list):
        return [payload]

    return []


def process_sample(sample_index: int, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    prices = sample.get("prices")
    if not isinstance(prices, list):
        return None

    emissions = sanitize_emissions(prices)
    if not emissions:
        return None

    stats = compute_statistics(list(emissions.values()))
    if stats["active_subnets"] == 0:
        return None

    requested_time = sample.get("requested_time")
    block_timestamp = sample.get("block_timestamp_utc")
    closest_block = sample.get("closest_block")

    sample_payload: Dict[str, Any] = {
        "sample_index": sample_index,
        "requested_time": requested_time if isinstance(requested_time, str) else None,
        "block_timestamp_utc": block_timestamp if isinstance(block_timestamp, str) else None,
        "closest_block": closest_block if isinstance(closest_block, int) else None,
        "emissions": emissions,
        "statistics": stats,
    }
    return sample_payload


def build_summary(samples: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if len(samples) < 2:
        return None

    active_counts = [s["statistics"]["active_subnets"] for s in samples if s["statistics"]["active_subnets"] is not None]
    totals = [s["statistics"]["total_emission_rate"] for s in samples if s["statistics"]["total_emission_rate"] is not None]

    if not active_counts and not totals:
        return None

    summary: Dict[str, Any] = {"observations": len(samples)}
    if active_counts:
        summary["active_subnets_min"] = min(active_counts)
        summary["active_subnets_max"] = max(active_counts)
    if totals:
        summary["total_emission_rate_min"] = min(totals)
        summary["total_emission_rate_max"] = max(totals)
        summary["total_emission_rate_avg"] = sum(totals) / len(totals)
    return summary


def build_output(source_path: Path, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    samples_raw = derive_samples(payload)
    if not samples_raw:
        return None, "no samples found"

    processed_samples: List[Dict[str, Any]] = []
    for index, sample in enumerate(samples_raw):
        processed = process_sample(index, sample)
        if processed:
            processed_samples.append(processed)

    if not processed_samples:
        return None, "no samples contained usable emissions data"

    primary = processed_samples[0]
    network = payload.get("network")
    if not isinstance(network, str):
        network = None
    metadata = {
        "collection_method": COLLECTION_METHOD,
        "date": derive_date_token(source_path, payload),
        "network": network,
        "timestamp": primary["block_timestamp_utc"],
        "closest_block": primary["closest_block"],
        "requested_time": primary["requested_time"],
        "samples_per_day": payload.get("samples_per_day") if isinstance(payload.get("samples_per_day"), int) else len(samples_raw),
        "primary_sample_index": primary["sample_index"],
    }

    output: Dict[str, Any] = {
        "metadata": metadata,
        "statistics": primary["statistics"],
        "samples": processed_samples,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    summary = build_summary(processed_samples)
    if summary:
        output["summary"] = summary

    return output, None


def write_output(destination_dir: Path, source_path: Path, output: Dict[str, Any]) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    date_token = output["metadata"]["date"]
    destination = destination_dir / f"emissions_v2_{date_token}.json"
    destination.write_text(json.dumps(output, indent=2))


def translate(input_path: Path, output_dir: Path, dry_run: bool) -> Tuple[int, List[Tuple[Path, str]]]:
    processed = 0
    skipped: List[Tuple[Path, str]] = []

    for path in iter_input_paths(input_path):
        payload, error = load_json(path)
        if error:
            skipped.append((path, error))
            continue

        output, reason = build_output(path, payload)
        if reason:
            skipped.append((path, reason))
            continue

        processed += 1
        if not dry_run and output is not None:
            write_output(output_dir, path, output)

    return processed, skipped


def main() -> None:
    args = parse_args()

    processed, skipped = translate(args.input, args.output, args.dry_run)
    print(f"Translated {processed} file(s).")
    if not args.dry_run:
        print(f"Output directory: {args.output}")

    if skipped:
        print("Skipped:")
        for path, reason in skipped:
            print(f"  - {path}: {reason}")


if __name__ == "__main__":
    main()
