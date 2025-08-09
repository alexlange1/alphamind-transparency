#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Dict, Optional
import os
import json


@dataclass(frozen=True)
class PriceSnapshot:
    # TAO-denominated prices by netuid
    prices_by_netuid: Dict[int, float]


def parse_btcli_table(text: str) -> Dict[int, float]:
    prices: Dict[int, float] = {}
    for line in text.splitlines():
        if "│" not in line:
            continue
        parts = [p.strip() for p in line.split("│")]
        if not parts or not parts[0].isdigit() or len(parts) < 3:
            continue
        try:
            netuid = int(parts[0])
        except Exception:
            continue
        price_col = parts[2]
        num = ""
        for ch in price_col:
            if ch.isdigit() or ch == ".":
                num += ch
            elif num:
                break
        try:
            prices[netuid] = float(num)
        except Exception:
            prices[netuid] = 0.0
    return prices


def read_prices_from_btcli(btcli_path: str, network: str = "finney", timeout_sec: int = 15) -> PriceSnapshot:
    try:
        proc = subprocess.run(
            [btcli_path, "subnets", "list", "--network", network],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        prices = parse_btcli_table(proc.stdout)
        return PriceSnapshot(prices_by_netuid=prices)
    except Exception:
        # Fallback: if an environment-provided last-known-good exists, use it
        cache_path = os.environ.get("AM_LAST_PRICES_JSON")
        if cache_path and os.path.exists(cache_path):
            try:
                data = json.loads(open(cache_path, "r", encoding="utf-8").read())
                prices = {int(k): float(v) for k, v in data.items()}
                return PriceSnapshot(prices_by_netuid=prices)
            except Exception:
                pass
        # Otherwise empty
        return PriceSnapshot(prices_by_netuid={})


