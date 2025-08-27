#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .tao20.price_feed import read_prices_from_btcli
from .tao20.index_design import demo_weights
from .tao20.models import EmissionsReport
from .tao20.validator import compute_index_weights_from_reports


def cmd_prices(args: argparse.Namespace) -> None:
    snap = read_prices_from_btcli(args.btcli, network=args.network)
    print(json.dumps(snap.prices_by_netuid, indent=2, sort_keys=True))


def cmd_demo_weights(args: argparse.Namespace) -> None:
    w = demo_weights(n=args.n)
    print(json.dumps(w, indent=2, sort_keys=True))

def cmd_aggregate_demo(args: argparse.Namespace) -> None:
    # Build a tiny demo: two miners report slightly different emissions for 5 nets
    rep1 = EmissionsReport(
        snapshot_ts="2025-01-01T00:00:00Z",
        emissions_by_netuid={1: 100.0, 2: 80.0, 3: 60.0, 4: 40.0, 5: 20.0},
        miner_id="m1",
        stake_tao=100.0,
    )
    rep2 = EmissionsReport(
        snapshot_ts="2025-01-01T00:00:00Z",
        emissions_by_netuid={1: 98.0, 2: 79.0, 3: 61.0, 4: 41.0, 5: 19.5},
        miner_id="m2",
        stake_tao=50.0,
    )
    weights = compute_index_weights_from_reports([rep1, rep2], top_n=args.n)
    print(json.dumps(weights, indent=2, sort_keys=True))


def main() -> None:
    p = argparse.ArgumentParser(description="TAO20 subnet prototype CLI")
    sub = p.add_subparsers()

    sp = sub.add_parser("prices", help="Read prices from btcli table")
    sp.add_argument("--btcli", required=True, help="Path to btcli binary")
    sp.add_argument("--network", default="finney")
    sp.set_defaults(func=cmd_prices)

    sp2 = sub.add_parser("demo-weights", help="Print demo emissions weights for top N")
    sp2.add_argument("--n", type=int, default=20)
    sp2.set_defaults(func=cmd_demo_weights)

    sp3 = sub.add_parser("aggregate-demo", help="Stake-weighted median over demo emissions reports")
    sp3.add_argument("--n", type=int, default=5)
    sp3.set_defaults(func=cmd_aggregate_demo)

    args = p.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()


