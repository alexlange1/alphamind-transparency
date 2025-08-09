import json
import time
from pathlib import Path

from subnet.tao20.models import EmissionsReport
from subnet.tao20.reports import PriceReport
from subnet.validator.service import compute_rolling_emissions, consensus_prices_with_twap, _to_bps


def _ts(days_ago: int = 0) -> str:
    t = int(time.time()) - days_ago * 24 * 3600
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def test_emissions_eligibility(tmp_path: Path):
    # Net 1 has 90 days, net 2 has 60 days
    reps = []
    for d in range(90):
        ts = _ts(90 - d)
        reps.append(EmissionsReport(snapshot_ts=ts, emissions_by_netuid={1: 100.0}, miner_id=f"m{d}", stake_tao=10.0))
    for d in range(60):
        ts = _ts(60 - d)
        reps.append(EmissionsReport(snapshot_ts=ts, emissions_by_netuid={2: 50.0}, miner_id=f"n{d}", stake_tao=10.0))

    avg, elig = compute_rolling_emissions(tmp_path, reps)
    assert 1 in avg and 2 in avg
    assert elig.get(1) is True
    assert elig.get(2) is False


def test_price_quorum_and_outlier(tmp_path: Path):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Three miners; A and B honest near 10; C outlier 12
    pr_a = PriceReport(ts=now, prices_by_netuid={1: 10.0}, miner_id="A", block=123, block_time=now)
    pr_b = PriceReport(ts=now, prices_by_netuid={1: 10.1}, miner_id="B", block=124, block_time=now)
    pr_c = PriceReport(ts=now, prices_by_netuid={1: 12.0}, miner_id="C", block=125, block_time=now)
    stake_by_miner = {"A": 100.0, "B": 50.0, "C": 5.0}
    prices, quorum, staleness = consensus_prices_with_twap(
        [pr_a, pr_b, pr_c],
        stake_by_miner=stake_by_miner,
        window_minutes=30,
        outlier_k=5.0,
        quorum_threshold=0.33,
        price_band_pct=0.10,
        stale_sec=120,
        out_dir=None,
    )
    assert 1 in prices
    assert abs(prices[1] - 10.05) < 0.2  # around the median of A/B
    assert quorum[1] > 0.9


def test_price_quorum_fallback_all_time(tmp_path: Path):
    # Only low-stake miner within window; others old → coverage fails, fallback to all-time
    now = int(time.time())
    old = now - 2 * 3600  # older than 30-min window but still in all-time set
    pr_old_a = PriceReport(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old)), prices_by_netuid={1: 10.0}, miner_id="A", block=111, block_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old)))
    pr_old_b = PriceReport(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old)), prices_by_netuid={1: 10.2}, miner_id="B", block=112, block_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old)))
    pr_now_c = PriceReport(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), prices_by_netuid={1: 9.9}, miner_id="C", block=130, block_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)))
    stake_by_miner = {"A": 100.0, "B": 50.0, "C": 5.0}
    prices, quorum, staleness = consensus_prices_with_twap(
        [pr_old_a, pr_old_b, pr_now_c],
        stake_by_miner=stake_by_miner,
        window_minutes=30,
        outlier_k=5.0,
        quorum_threshold=0.5,
        price_band_pct=0.2,
        stale_sec=120,
        out_dir=None,
    )
def test_weights_bps_and_top20():
    # Emulate service: trim to top-20 first, then convert to bps and ensure sum is 10_000
    weights = {i: (21 - i) / 231.0 for i in range(1, 30)}  # descending
    # first normalize weights
    denom = sum(weights.values())
    w = {k: v / denom for k, v in weights.items()}
    items = sorted(w.items(), key=lambda kv: kv[1], reverse=True)[:20]
    bps_trim, w_trim = _to_bps(dict(items))
    assert sum(bps_trim.values()) == 10000
    assert len(bps_trim) == 20


