import json
import time
from pathlib import Path

from subnet.validator.service import aggregate_and_emit


def test_weightset_has_20_constituents_and_10000_bps(tmp_path: Path):
    # Seed minimal emissions reports across >20 nets so aggregate selects top-20
    # Reuse existing demo by writing multiple days using miner stake weighting - rely on service normalization
    # Here we directly place 20+ averages by constructing reports today
    from subnet.tao20.models import EmissionsReport
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reps = []
    for i in range(1, 25):
        reps.append(EmissionsReport(snapshot_ts=ts, emissions_by_netuid={i: float(100 - i)}, miner_id=f"m{i}", stake_tao=10.0))
        # match loader glob: emissions_*_*.json
        (tmp_path / f"emissions_{i}_test.json").write_text(reps[-1].to_json(), encoding="utf-8")
    # Bypass 90-day eligibility in test using overrides
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    overrides = {str(i): True for i in range(1, 100)}
    (state / "eligibility_overrides.json").write_text(json.dumps(overrides), encoding="utf-8")
    out = tmp_path / "weights.json"
    aggregate_and_emit(tmp_path, out, top_n=20)
    ws_files = list(tmp_path.glob("weightset_epoch_*.json"))
    assert ws_files, "expected epoch weightset file"
    data = json.loads(ws_files[0].read_text(encoding="utf-8"))
    const = data.get("constituents") or []
    assert len(const) == 20
    bps_sum = sum(int(c.get("weight_bps", 0)) for c in const)
    assert bps_sum == 10000


def test_weightset_hash_is_deterministic(tmp_path: Path):
    # Create fixed inputs; run aggregate twice; hashes must match
    from subnet.tao20.models import EmissionsReport
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rep = EmissionsReport(snapshot_ts=ts, emissions_by_netuid={1: 100.0, 2: 90.0, 3: 80.0, 4: 70.0, 5: 60.0, 6: 50.0, 7: 40.0, 8: 30.0, 9: 20.0, 10: 10.0,
                                                                11: 9.0, 12: 8.0, 13: 7.0, 14: 6.0, 15: 5.0, 16: 4.0, 17: 3.0, 18: 2.0, 19: 1.0, 20: 0.9}, miner_id="m", stake_tao=10.0)
    (tmp_path / "emissions_fixed.json").write_text(rep.to_json(), encoding="utf-8")
    out = tmp_path / "weights.json"
    aggregate_and_emit(tmp_path, out, top_n=20)
    w1 = list(tmp_path.glob("weightset_epoch_*.sha256"))[0].read_text(encoding="utf-8").strip()
    # Re-run without changing inputs
    aggregate_and_emit(tmp_path, out, top_n=20)
    w2 = list(tmp_path.glob("weightset_epoch_*.sha256"))[0].read_text(encoding="utf-8").strip()
    assert w1 == w2


def test_epoch_rolls_every_14_days():
    from subnet.sim.epoch import current_epoch_index, REBALANCE_PERIOD_SECS, EPOCH_ANCHOR_UNIX
    base = EPOCH_ANCHOR_UNIX  # exact anchor
    e0 = current_epoch_index(base)
    e1 = current_epoch_index(base + REBALANCE_PERIOD_SECS - 1)
    e2 = current_epoch_index(base + REBALANCE_PERIOD_SECS + 1)
    assert e0 == e1
    assert e2 == e0 + 1


