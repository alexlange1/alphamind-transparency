from pathlib import Path

from subnet.sim.vault import VaultState, mint_tao_extended


def test_residuals_nonzero_and_bounded(monkeypatch):
    # Uneven pools and weights → expect some residuals
    prices = {1: 10.0, 2: 5.0, 3: 1.0}
    weights = {1: 0.6, 2: 0.3, 3: 0.1}
    state = VaultState(holdings={1: 0.0, 2: 0.0, 3: 0.0}, tao20_supply=1000.0, last_nav_tao=100.0)
    # Force deterministic epsilon
    monkeypatch.setenv("AM_RESIDUAL_EPSILON_BPS", "5")
    s1, result = mint_tao_extended(100.0, weights, prices, state)
    # Sum of residual value should be small vs input (a few bps)
    total_res_val = sum(r.qty * prices.get(r.uid, 0.0) for r in result.residuals)
    assert total_res_val <= 100.0 * 0.01  # <= 100 bps of input
    # Deterministic across repeated runs
    s2, result2 = mint_tao_extended(100.0, weights, prices, state)
    vals1 = sorted((r.uid, round(r.qty, 9)) for r in result.residuals)
    vals2 = sorted((r.uid, round(r.qty, 9)) for r in result2.residuals)
    assert vals1 == vals2


