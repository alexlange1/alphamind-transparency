#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import subprocess
import time
from typing import Dict

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_PATH = os.path.join(PROJECT_DIR, "state", "tao20_portfolio.json")
NAV_HISTORY = os.path.join(PROJECT_DIR, "nav_history.tsv")
BTCLI_BIN = "/Users/alexanderlange/.venvs/alphamind/bin/btcli"


def get_prices_from_table() -> Dict[int, float]:
    proc = subprocess.run(
        [BTCLI_BIN, "subnets", "list", "--network", "finney"],
        check=True,
        capture_output=True,
        text=True,
    )
    text = proc.stdout
    prices: Dict[int, float] = {}
    for line in text.splitlines():
        if "│" not in line:
            continue
        parts = [p.strip() for p in line.split("│")]
        if not parts or not parts[0].isdigit():
            continue
        if len(parts) < 3:
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


def ensure_nav_header():
    if not os.path.exists(NAV_HISTORY):
        with open(NAV_HISTORY, "w", encoding="utf-8", newline="") as f:
            f.write("timestamp\tnav_tao\tcash_tao\tpositions_json\n")


def append_nav_row(nav: float, cash: float, positions_json: str) -> None:
    ensure_nav_header()
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(NAV_HISTORY, "a", encoding="utf-8", newline="") as f:
        f.write(f"{ts}\t{nav}\t{cash}\t{positions_json}\n")


def regenerate_chart():
    subprocess.run([
        "/Users/alexanderlange/.venvs/alphamind/bin/python",
        os.path.join(PROJECT_DIR, "gen_nav_html.py"),
    ], check=True)


def main() -> None:
    try:
        portfolio = json.load(open(PORTFOLIO_PATH, "r", encoding="utf-8"))
    except Exception:
        portfolio = {"cash_tao": 0.0, "alpha": {}}

    prices = get_prices_from_table()
    cash = float(portfolio.get("cash_tao", 0.0))
    alpha = portfolio.get("alpha") or {}

    nav = cash
    for k, v in alpha.items():
        try:
            n = int(k)
            a = float(v)
        except Exception:
            continue
        nav += a * float(prices.get(n, 0.0))

    append_nav_row(nav, cash, json.dumps(alpha, ensure_ascii=False))
    regenerate_chart()


if __name__ == "__main__":
    main()


