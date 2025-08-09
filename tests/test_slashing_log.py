import json
import time
from pathlib import Path

from subnet.tao20.models import EmissionsReport
from subnet.tao20.reports import PriceReport
from subnet.validator.service import _aggregate_daily_emissions_by_day, consensus_prices_with_twap


def test_emissions_slashing_log(tmp_path: Path):
    # Two miners; one outlier beyond band should be logged
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reps = [
        EmissionsReport(snapshot_ts=ts, emissions_by_netuid={1: 100.0}, miner_id="A", stake_tao=100.0),
        EmissionsReport(snapshot_ts=ts, emissions_by_netuid={1: 1000.0}, miner_id="B", stake_tao=50.0),
    ]
    # Force band to be tight
    import os
    os.environ["AM_EMISSIONS_BAND_PCT"] = "0.2"
    _aggregate_daily_emissions_by_day(reps, out_dir=tmp_path)
    logp = tmp_path / "slashing_log.jsonl"
    assert logp.exists()
    lines = [json.loads(x) for x in logp.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert any(l.get("type") in ("emission_outlier", "emission_band_violation") for l in lines)


def test_price_slashing_log(tmp_path: Path):
    # Two miners; one stale should be logged
    now = int(time.time())
    old = now - 3600
    pr_old = PriceReport(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old)), prices_by_netuid={1: 10.0}, miner_id="A", block=1, block_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old)))
    pr_new = PriceReport(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), prices_by_netuid={1: 10.1}, miner_id="B", block=2, block_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)))
    prices, quorum, staleness = consensus_prices_with_twap([pr_old, pr_new], stake_by_miner={"A": 10.0, "B": 10.0}, window_minutes=30, outlier_k=5.0, quorum_threshold=0.1, price_band_pct=0.5, stale_sec=120, out_dir=tmp_path)
    logp = tmp_path / "slashing_log.jsonl"
    assert logp.exists()
    lines = [json.loads(x) for x in logp.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert any(l.get("type") == "price_stale" for l in lines)


