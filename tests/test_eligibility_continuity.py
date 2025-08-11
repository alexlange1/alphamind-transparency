import time
from pathlib import Path

from subnet.tao20.models import EmissionsReport
from subnet.validator.service import compute_rolling_emissions


def _ts(days_ago: int = 0) -> str:
    t = int(time.time()) - days_ago * 24 * 3600
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def test_gappy_series_excluded(tmp_path: Path):
    reps = []
    # Net 1: 90 days continuous
    for d in range(90):
        reps.append(EmissionsReport(snapshot_ts=_ts(90 - d), emissions_by_netuid={1: 10.0}, miner_id=f"m{d}", stake_tao=10.0))
    # Net 2: 91 days with a gap day (emission zero/missing)
    for d in range(91):
        if d == 45:
            continue
        reps.append(EmissionsReport(snapshot_ts=_ts(91 - d), emissions_by_netuid={2: 10.0}, miner_id=f"n{d}", stake_tao=10.0))
    avg, elig = compute_rolling_emissions(tmp_path, reps)
    assert elig.get(1) is True
    assert elig.get(2) is False


def test_override_included(tmp_path: Path):
    # Write override
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "eligibility_overrides.json").write_text("{""2"": true}")
    reps = []
    # Net 2: only 10 days but overridden
    for d in range(10):
        reps.append(EmissionsReport(snapshot_ts=_ts(10 - d), emissions_by_netuid={2: 10.0}, miner_id=f"n{d}", stake_tao=10.0))
    avg, elig = compute_rolling_emissions(tmp_path, reps)
    assert elig.get(2) is True


def test_boundary_cases(tmp_path: Path):
    reps = []
    # Exactly 90 days continuous for uid=3
    for d in range(90):
        reps.append(EmissionsReport(snapshot_ts=_ts(90 - d), emissions_by_netuid={3: 1.0}, miner_id=f"a{d}", stake_tao=1.0))
    # 89 days for uid=4
    for d in range(89):
        reps.append(EmissionsReport(snapshot_ts=_ts(89 - d), emissions_by_netuid={4: 1.0}, miner_id=f"b{d}", stake_tao=1.0))
    # 90 with one explicit zero day in the middle for uid=5 -> treat as gap
    for d in range(90):
        ts = _ts(90 - d)
        val = 0.0 if d == 45 else 1.0
        reps.append(EmissionsReport(snapshot_ts=ts, emissions_by_netuid={5: val}, miner_id=f"c{d}", stake_tao=1.0))
    avg, elig = compute_rolling_emissions(tmp_path, reps)
    assert elig.get(3) is True
    assert elig.get(4) is False
    assert elig.get(5) is False


