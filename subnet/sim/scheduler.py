#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from pathlib import Path

from ..validator.service import aggregate_and_emit
from .epoch import current_epoch_id, EpochState
from ..tao20.models import WeightSet
from ..sim.vault import load_vault, save_vault, apply_management_fee
from ..validator.scoreboard import Scoreboard


def daily_snapshot_and_aggregate(out_dir: Path) -> None:
    # For now, just aggregate existing reports daily
    weights_file = out_dir / "weights.json"
    aggregate_and_emit(out_dir, weights_file, top_n=20)
    # Finalize scoreboard daily (idempotent)
    try:
        scb = Scoreboard(out_dir)
        scb.finalize_daily()
    except Exception:
        pass


def run_scheduler() -> None:
    out_dir = Path(os.environ.get("AM_OUT_DIR", "/Users/alexanderlange/alphamind/subnet/out"))
    state_file = out_dir / "epoch_state.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    while True:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        # Daily snapshot once per day
        daily_snapshot_and_aggregate(out_dir)

        # Accrue daily management fee if interval elapsed
        try:
            from ..validator.service import consensus_prices, load_price_reports
            prices = consensus_prices(load_price_reports(out_dir))
            vpath = out_dir / "vault_state.json"
            state = load_vault(vpath)
            if state is not None:
                state = apply_management_fee(prices, state)
                save_vault(vpath, state)
        except Exception:
            pass

        # Epoch rollover: persist WeightSet every 14 days
        eid = current_epoch_id()
        state = EpochState(epoch_id=eid, last_aggregation_ts=now)
        state_file.write_text(state.to_json(), encoding="utf-8")
        try:
            # Persist a snapshot of weights for this epoch if available
            wjson = (out_dir / "weights.json").read_text(encoding="utf-8")
            import json as _json
            data = _json.loads(wjson)
            weights = {int(k): float(v) for k, v in (data.get("weights") or {}).items()}
            ws = WeightSet(epoch_id=eid, as_of_ts=now, weights=weights)
            (out_dir / f"weightset_epoch_{eid}.json").write_text(ws.to_json(), encoding="utf-8")
        except Exception:
            pass

        # Sleep ~24h
        time.sleep(24 * 60 * 60)


if __name__ == "__main__":
    run_scheduler()


