#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .tao20.price_feed import read_prices_from_btcli

from .tao20.models import EmissionsReport
from .tao20.validator import compute_index_weights_from_reports


def cmd_prices(args: argparse.Namespace) -> None:
    snap = read_prices_from_btcli(args.btcli, network=args.network)
    print(json.dumps(snap.prices_by_netuid, indent=2, sort_keys=True))







def main() -> None:
    p = argparse.ArgumentParser(description="TAO20 subnet prototype CLI")
    sub = p.add_subparsers()

    sp = sub.add_parser("prices", help="Read prices from btcli table")
    sp.add_argument("--btcli", required=True, help="Path to btcli binary")
    sp.add_argument("--network", default="finney")
    sp.set_defaults(func=cmd_prices)





    args = p.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()


