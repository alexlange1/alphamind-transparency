#!/usr/bin/env python3
"""Scan price snapshots and report netuids lacking validator matches."""

import argparse
import json
from pathlib import Path


def load_snapshot(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[warn] Cannot read {path}: {exc}")
        return None
    idx = text.find("{")
    if idx == -1:
        print(f"[warn] No JSON object in {path}")
        return None
    try:
        return json.loads(text[idx:])
    except json.JSONDecodeError as exc:
        print(f"[warn] Invalid JSON in {path}: {exc}")
        return None


def main():
    parser = argparse.ArgumentParser(description="List files/netuids missing validator matches")
    parser.add_argument("root", nargs="?", default="outputs", help="Directory with price_*.json files (default: outputs)")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Input directory {root} does not exist")

    missing = []
    for path in sorted(root.glob("prices_*.json")):
        data = load_snapshot(path)
        if not isinstance(data, dict):
            continue
        prices = data.get("prices")
        if not isinstance(prices, list):
            continue
        day_missing = []
        for entry in prices:
            if not isinstance(entry, dict):
                continue
            netuid = entry.get("netuid")
            validators = entry.get("validators")
            matches = None
            if isinstance(validators, dict):
                matches = validators.get("matched_coldkeys") or validators.get("matches")
            if not matches:
                day_missing.append(netuid)
        if day_missing:
            missing.append((path.name, day_missing))

    if not missing:
        print("All snapshots contain validator matches for every netuid.")
        return

    print("Days with missing validator matches:")
    for filename, netuids in missing:
        readable = ", ".join(str(n) for n in netuids if n is not None)
        print(f"  {filename}: {readable}")


if __name__ == "__main__":
    main()
