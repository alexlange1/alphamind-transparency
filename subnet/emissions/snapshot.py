#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class EmissionSnapshot:
    # ts in ISO8601Z
    ts: str
    # TAO per day (or per period normalized to day) keyed by netuid
    emissions_by_netuid: Dict[int, float]


def _parse_table_emission(text: str, emission_col_index: int) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for line in text.splitlines():
        if "│" not in line:
            continue
        parts = [p.strip() for p in line.split("│")]
        if not parts or not parts[0].isdigit():
            continue
        try:
            netuid = int(parts[0])
        except Exception:
            continue
        col = parts[emission_col_index] if emission_col_index < len(parts) else parts[-1]
        num = ""
        for ch in col:
            if ch.isdigit() or ch == ".":
                num += ch
            elif num:
                break
        try:
            out[netuid] = float(num)
        except Exception:
            out[netuid] = 0.0
    return out


def take_snapshot(btcli_path: str, network: str = "finney", emission_col_index: int = 4) -> EmissionSnapshot:
    proc = subprocess.run(
        [btcli_path, "subnets", "list", "--network", network],
        check=True,
        capture_output=True,
        text=True,
    )
    em = _parse_table_emission(proc.stdout, emission_col_index=emission_col_index)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return EmissionSnapshot(ts=ts, emissions_by_netuid=em)


def take_snapshot_map() -> Dict[int, float]:
    """Convenience: read btcli path from env and return {uid: daily_emission_tao}.

    Non-breaking addition for miner loop integration.
    """
    import os as _os
    btcli = _os.environ.get("AM_BTCLI", "/Users/alexanderlange/.venvs/alphamind/bin/btcli")
    net = _os.environ.get("AM_NETWORK", "finney")
    try:
        snap = take_snapshot(btcli, network=net)
        return snap.emissions_by_netuid
    except Exception:
        return {}


def append_snapshot_tsv(out_dir: Path, snap: EmissionSnapshot) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "emissions_daily.tsv"
    header = ["timestamp", "netuid", "emission_tao_per_day"]
    write_header = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        if write_header:
            w.writerow(header)
        for k, v in sorted(snap.emissions_by_netuid.items()):
            w.writerow([snap.ts, k, v])
    return path


def compute_rolling_14d(out_dir: Path) -> Path:
    """Compute 14d average emissions by netuid from emissions_daily.tsv -> emissions_14d.tsv"""
    daily = out_dir / "emissions_daily.tsv"
    out = out_dir / "emissions_14d.tsv"
    if not daily.exists():
        return out
    # Read last 14 days into memory
    rows: List[Tuple[str, int, float]] = []
    with open(daily, "r", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            try:
                ts = row["timestamp"]
                netuid = int(row["netuid"])
                val = float(row["emission_tao_per_day"]) or 0.0
            except Exception:
                continue
            rows.append((ts, netuid, val))
    # Keep last 14 distinct days by timestamp date prefix
    from collections import defaultdict
    by_day: Dict[str, Dict[int, float]] = defaultdict(dict)
    for ts, nid, val in rows:
        day = ts[:10]
        by_day[day][nid] = val
    days = sorted(by_day.keys())[-14:]
    sum_map: Dict[int, float] = defaultdict(float)
    count_map: Dict[int, int] = defaultdict(int)
    for d in days:
        for nid, val in by_day[d].items():
            sum_map[nid] += val
            count_map[nid] += 1
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["netuid", "avg_14d_emission_tao_per_day", "days_counted"])
        for nid in sorted(sum_map.keys()):
            c = count_map[nid]
            avg = (sum_map[nid] / c) if c else 0.0
            w.writerow([nid, avg, c])
    return out


def compute_eligibility_3m(out_dir: Path) -> Path:
    """Simple eligibility: subnet appears with nonzero daily emission on >= 90 days in the last ~3 months."""
    daily = out_dir / "emissions_daily.tsv"
    out = out_dir / "eligibility_3m.tsv"
    if not daily.exists():
        return out
    import csv as _csv
    from collections import defaultdict
    seen_days: Dict[int, int] = defaultdict(int)
    with open(daily, "r", encoding="utf-8") as f:
        r = _csv.DictReader(f, delimiter="\t")
        for row in r:
            try:
                nid = int(row["netuid"]) 
                val = float(row["emission_tao_per_day"]) or 0.0
            except Exception:
                continue
            if val > 0:
                seen_days[nid] += 1
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f, delimiter="\t")
        w.writerow(["netuid", "eligible_3m"])
        for nid in sorted(seen_days.keys()):
            w.writerow([nid, 1 if seen_days[nid] >= 90 else 0])
    return out


