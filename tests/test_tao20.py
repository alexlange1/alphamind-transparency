import os
from pathlib import Path
from subnet.validator.service import _median, _mad
from subnet.sim.vault import VaultState, compute_nav, apply_mint_with_tao, apply_mint_in_kind, apply_management_fee


def test_median_mad():
    vals = [1, 1, 2, 2, 100]
    m = _median(vals)
    assert m == 2
    d = _mad(vals, m)
    assert d >= 0


def test_vault_mint_and_fees(tmp_path: Path):
    prices = {1: 2.0, 2: 1.0}
    state = VaultState(holdings={1: 0.0, 2: 0.0}, tao20_supply=100.0, last_nav_tao=1.0)
    # Mint via TAO 100 with 0.2% fee -> fee 0.2
    state = apply_mint_with_tao(100.0, weights={1: 0.5, 2: 0.5}, prices=prices, state=state, fee_bps=20)
    assert state.fees_tx_tao > 0
    # In-kind mint
    state = apply_mint_in_kind({1: 10.0}, prices, state, fee_bps=20)
    assert state.fees_tx_tao > 0
    # Apply 30-day mgmt fee
    pre_supply = state.tao20_supply
    state.last_mgmt_ts = "2025-01-01T00:00:00Z"
    state = apply_management_fee(prices, state, now_iso_ts="2025-01-31T00:00:00Z")
    assert state.tao20_supply > pre_supply
    assert state.fees_mgmt_tao > 0


