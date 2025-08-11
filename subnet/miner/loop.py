#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List

from ..tao20.price_feed import read_prices_from_btcli, read_prices_items_from_btcli
from ..tao20.models import EmissionsReport
from ..tao20.reports import PriceReport, NavReport, PriceItem
from ..common.crypto import sign_message
from ..common.bt_signing import sign_with_hotkey
from ..emissions.snapshot import take_snapshot_map
from ..common.settings import get_settings


def calculate_nav(prices: List[PriceItem], total_supply: float) -> float:
    if not prices:
        return 0.0
    total_value = sum(item.price_in_tao for item in prices)
    return total_value / total_supply if total_supply > 0 else 0.0


def load_demo_emissions() -> Dict[int, float]:
    # Placeholder: will be replaced with real daily snapshot
    return {1: 100.0, 2: 80.0, 3: 60.0, 4: 40.0, 5: 20.0}


def _epoch_day(now_unix: int | None = None) -> int:
    try:
        from ..sim.epoch import EPOCH_SECONDS, ANCHOR_UNIX
        import time as _t
        if now_unix is None:
            now_unix = int(_t.time())
        into = (now_unix - ANCHOR_UNIX) % EPOCH_SECONDS
        return int(into // (24 * 3600))
    except Exception:
        return 0


def _sign_payload(payload: str, wallet: str | None, hotkey: str | None, secret: str) -> tuple[str, str, str]:
    # Returns (signature, signer, scheme)
    if wallet and hotkey:
        sw = sign_with_hotkey(payload.encode("utf-8"), wallet, hotkey)
        if sw:
            return sw[0], sw[1], "HOTKEY"
    # fallback HMAC if configured
    if secret:
        sig = sign_message(secret, payload)
        return sig, "", "HMAC"
    return "", "", ""


def run_once(out_dir: Path, btcli_path: str, miner_id: str, secret: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    emit_emissions(out_dir, miner_id, secret, ts)
    emit_prices(out_dir, btcli_path, miner_id, secret, ts)
    emit_nav(out_dir, miner_id, ts)


def emit_emissions(out_dir: Path, miner_id: str, secret: str, ts: str) -> None:
    # Emissions
    do_demo = os.environ.get("AM_DEMO", "0") == "1"
    if do_demo:
        emissions = load_demo_emissions()
    else:
        emissions = take_snapshot_map()
    
    stake_tao = float(os.environ.get("AM_STAKE_TAO", "100.0"))

    erep = EmissionsReport(
        snapshot_ts=ts,
        emissions_by_netuid=emissions,
        miner_id=miner_id,
        stake_tao=stake_tao,
        schema_version="1.0.0",
        epoch_day=_epoch_day(),
        miner_hotkey=os.environ.get("AM_HOTKEY", ""),
        sig_scheme="",
    )
    payload = erep.to_json()
    wallet = os.environ.get("AM_WALLET")
    hotkey = os.environ.get("AM_HOTKEY")
    sig, signer, scheme = _sign_payload(payload, wallet, hotkey, secret)
    erep = EmissionsReport.from_json(payload)
    erep = EmissionsReport(
        snapshot_ts=erep.snapshot_ts,
        emissions_by_netuid=erep.emissions_by_netuid,
        miner_id=erep.miner_id,
        stake_tao=erep.stake_tao,
        signature=sig,
        signer_ss58=signer,
        schema_version="1.0.0",
        epoch_day=_epoch_day(),
        miner_hotkey=hotkey or "",
        sig_scheme=scheme,
    )
    out_name = f"emissions_{time.strftime('%Y%m%d', time.gmtime())}_{(hotkey or miner_id)}.json"
    (out_dir / out_name).write_text(erep.to_json(), encoding="utf-8")


def emit_prices(out_dir: Path, btcli_path: str, miner_id: str, secret: str, ts: str) -> None:
    # Prices
    wallet = os.environ.get("AM_WALLET")
    hotkey = os.environ.get("AM_HOTKEY")
    items = read_prices_items_from_btcli(btcli_path)
    # also legacy map for compatibility
    pmap = read_prices_from_btcli(btcli_path).prices_by_netuid
    prep = PriceReport(ts=ts, prices_by_netuid=pmap, miner_id=miner_id, schema_version="1.0.0", prices=items)
    payload_p = prep.to_json()
    sigp, signerp, schemep = _sign_payload(payload_p, wallet, hotkey, secret)
    prep = PriceReport.from_json(payload_p)
    prep = PriceReport(
        ts=prep.ts,
        prices_by_netuid=prep.prices_by_netuid,
        miner_id=prep.miner_id,
        block=prep.block,
        block_time=prep.block_time,
        signature=sigp,
        signer_ss58=signerp,
        schema_version="1.0.0",
        prices=items,
    )
    out_name_p = f"prices_{time.strftime('%Y%m%d_%H%M', time.gmtime())}_{(hotkey or miner_id)}.json"
    (out_dir / out_name_p).write_text(prep.to_json(), encoding="utf-8")


def emit_nav(out_dir: Path, miner_id: str, ts: str) -> None:
    # NAV (demo placeholder)
    wallet = os.environ.get("AM_WALLET")
    hotkey = os.environ.get("AM_HOTKEY")

    # Fetch real prices to calculate NAV
    btcli_path = os.environ.get("AM_BTCLI", "/Users/alexanderlange/.venvs/alphamind/bin/btcli")
    price_items = read_prices_items_from_btcli(btcli_path)
    total_supply = 1.0  # Placeholder for total TAO20 supply
    nav_per_token = calculate_nav(price_items, total_supply)

    nrep = NavReport(ts=ts, nav_per_token_tao=nav_per_token, total_supply=total_supply, miner_id=miner_id)
    if wallet and hotkey:
        sw = sign_with_hotkey(nrep.to_json().encode("utf-8"), wallet, hotkey)
        if sw:
            nrep = NavReport.from_json(nrep.to_json())
            nrep = NavReport(ts=nrep.ts, nav_per_token_tao=nrep.nav_per_token_tao, total_supply=nrep.total_supply,
                             miner_id=nrep.miner_id, signature=sw[0], signer_ss58=sw[1])
    (out_dir / f"nav_{miner_id}_{ts}.json").write_text(nrep.to_json(), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="TAO20 miner emitter")
    p.add_argument("--emit-emissions-once", action="store_true", help="Emit a single EmissionsReport and exit")
    p.add_argument("--emit-prices-once", action="store_true", help="Emit a single PriceReport and exit")
    p.add_argument("--interval-sec", type=int, default=int(os.environ.get("AM_PRICE_INTERVAL_SEC", "60")),
                     help="Interval for periodic price emits (unused for one-shot)")
    args = p.parse_args()

    out_dir = Path(os.environ.get("AM_OUT_DIR", "/Users/alexanderlange/alphamind/subnet/out"))
    btcli_path = os.environ.get("AM_BTCLI", "/Users/alexanderlange/.venvs/alphamind/bin/btcli")
    miner_id = os.environ.get("AM_MINER_ID", "miner-demo")
    secret = os.environ.get("AM_MINER_SECRET", "demo-secret")
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if args.emit_emissions_once and not args.emit_prices_once:
        emit_emissions(out_dir, miner_id, secret, ts)
        return

    if args.emit_prices_once and not args.emit_emissions_once:
        emit_prices(out_dir, btcli_path, miner_id, secret, ts)
        return

    # Default behavior: one combined run once (emissions, prices, nav)
    run_once(out_dir, btcli_path, miner_id, secret)


if __name__ == "__main__":
    main()


