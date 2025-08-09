#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict

from ..tao20.price_feed import read_prices_from_btcli
from ..tao20.models import EmissionsReport
from ..tao20.reports import PriceReport, NavReport
from ..common.crypto import sign_message
from ..common.bt_signing import sign_with_hotkey


def load_demo_emissions() -> Dict[int, float]:
    # Placeholder: will be replaced with real daily snapshot
    return {1: 100.0, 2: 80.0, 3: 60.0, 4: 40.0, 5: 20.0}


def run_once(out_dir: Path, btcli_path: str, miner_id: str, secret: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Emissions demo
    emissions = load_demo_emissions()
    rep = EmissionsReport(snapshot_ts=ts, emissions_by_netuid=emissions, miner_id=miner_id, stake_tao=100.0)
    payload = rep.to_json()
    # Prefer Bittensor hotkey signing when available (env AM_WALLET / AM_HOTKEY)
    wallet = os.environ.get("AM_WALLET")
    hotkey = os.environ.get("AM_HOTKEY")
    sig = None
    if wallet and hotkey:
        sw = sign_with_hotkey(payload.encode("utf-8"), wallet, hotkey)
        if sw:
            sig = sw[0]
            signer = sw[1]
    if not sig:
        sig = sign_message(secret, payload)
        signer = ""
    rep = EmissionsReport.from_json(payload)
    rep = EmissionsReport(
        snapshot_ts=rep.snapshot_ts,
        emissions_by_netuid=rep.emissions_by_netuid,
        miner_id=rep.miner_id,
        stake_tao=rep.stake_tao,
        signature=sig,
        signer_ss58=signer,
    )
    (out_dir / f"emissions_{miner_id}_{ts}.json").write_text(rep.to_json(), encoding="utf-8")

    # Prices
    snap = read_prices_from_btcli(btcli_path)
    pre = PriceReport(ts=ts, prices_by_netuid=snap.prices_by_netuid, miner_id=miner_id)
    # sign if hotkey available
    wallet = os.environ.get("AM_WALLET")
    hotkey = os.environ.get("AM_HOTKEY")
    if wallet and hotkey:
        sw = sign_with_hotkey(pre.to_json().encode("utf-8"), wallet, hotkey)
        if sw:
            pre = PriceReport.from_json(pre.to_json())
            pre = PriceReport(ts=pre.ts, prices_by_netuid=pre.prices_by_netuid, miner_id=pre.miner_id, signature=sw[0], signer_ss58=sw[1])
    else:
        pre = PriceReport.from_json(pre.to_json())
    (out_dir / f"prices_{miner_id}_{ts}.json").write_text(pre.to_json(), encoding="utf-8")

    # NAV (demo placeholder)
    nrep = NavReport(ts=ts, nav_per_token_tao=100.0, total_supply=1.0, miner_id=miner_id)
    if wallet and hotkey:
        sw = sign_with_hotkey(nrep.to_json().encode("utf-8"), wallet, hotkey)
        if sw:
            nrep = NavReport.from_json(nrep.to_json())
            nrep = NavReport(ts=nrep.ts, nav_per_token_tao=nrep.nav_per_token_tao, total_supply=nrep.total_supply, miner_id=nrep.miner_id, signature=sw[0], signer_ss58=sw[1])
    (out_dir / f"nav_{miner_id}_{ts}.json").write_text(nrep.to_json(), encoding="utf-8")


def main() -> None:
    out_dir = Path(os.environ.get("AM_OUT_DIR", "/Users/alexanderlange/alphamind/subnet/out"))
    btcli_path = os.environ.get("AM_BTCLI", "/Users/alexanderlange/.venvs/alphamind/bin/btcli")
    miner_id = os.environ.get("AM_MINER_ID", "miner-demo")
    secret = os.environ.get("AM_MINER_SECRET", "demo-secret")
    run_once(out_dir, btcli_path, miner_id, secret)


if __name__ == "__main__":
    main()


