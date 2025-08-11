import time
from pathlib import Path

from subnet.tao20.models import EmissionsReport
from subnet.validator.service import compute_rolling_emissions


def _ts(days_ago: int = 0) -> str:
    t = int(time.time()) - days_ago * 24 * 3600
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def test_rolling_14d_avg_and_90d_eligibility_enforced(tmp_path: Path):
    # Net 1: 120 days; Net 2: 60 days
    reps = []
    for d in range(120):
        reps.append(EmissionsReport(snapshot_ts=_ts(120 - d), emissions_by_netuid={1: 100.0}, miner_id=f"m{d}", stake_tao=10.0))
    for d in range(60):
        reps.append(EmissionsReport(snapshot_ts=_ts(60 - d), emissions_by_netuid={2: 50.0}, miner_id=f"n{d}", stake_tao=10.0))
    avg, elig = compute_rolling_emissions(tmp_path, reps)
    assert 1 in avg and 2 in avg
    assert elig.get(1) is True
    assert elig.get(2) is False


