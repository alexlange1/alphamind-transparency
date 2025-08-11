from pathlib import Path
import time
import os
import json
from fastapi.testclient import TestClient
from subnet.validator.api import app
from subnet.tao20.models import EmissionsReport


def _ts(days_ago: int = 0) -> str:
    t = int(time.time()) - days_ago * 24 * 3600
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _write_price_report(out_dir: Path, prices: dict[int, float], with_reserves: bool = False) -> None:
    from subnet.tao20.reports import PriceReport, PriceItem
    now = _ts(0)
    items = None
    if with_reserves:
        items = [PriceItem(uid=int(k), token=f"SN{k}", price_in_tao=float(v), pool_reserve_token="1000", pool_reserve_tao="1000") for k, v in prices.items()]
    pr = PriceReport(ts=now, prices_by_netuid={int(k): float(v) for k, v in prices.items()}, miner_id="m1", prices=items)
    (out_dir / f"prices_{int(time.time())}_m1.json").write_text(pr.to_json(), encoding="utf-8")


def _write_emissions_report(out_dir: Path, uids: list[int]) -> None:
    now = _ts(0)
    reps = EmissionsReport(snapshot_ts=now, emissions_by_netuid={int(u): 10.0 for u in uids}, miner_id="m1", stake_tao=10.0)
    (out_dir / f"emissions_{int(time.time())}_m1.json").write_text(reps.to_json(), encoding="utf-8")


def test_mint_tao_no_reserves_409(tmp_path: Path, monkeypatch):
    os.environ["AM_API_TOKEN"] = "dev"
    os.environ["AM_OUT_DIR"] = str(tmp_path)
    os.environ["AM_REQUIRE_RESERVES"] = "1"
    os.environ["AM_VALIDATOR_SELF_REFRESH"] = "0"
    # Seed emissions and prices without reserves info
    _write_emissions_report(tmp_path, [1, 2])
    _write_price_report(tmp_path, {1: 1.0, 2: 2.0}, with_reserves=False)
    client = TestClient(app)
    r = client.post("/mint-tao", headers={"Authorization": "Bearer dev"}, json={"in_dir": str(tmp_path), "amount_tao": 1.0})
    assert r.status_code == 409
    body = r.json()
    detail = body.get("detail", {})
    assert "missing_reserve_uids" in detail
    assert set(detail["missing_reserve_uids"]) == {1, 2}


def test_mint_tao_refresh_fills_ok(tmp_path: Path, monkeypatch):
    os.environ["AM_API_TOKEN"] = "dev"
    os.environ["AM_OUT_DIR"] = str(tmp_path)
    os.environ["AM_REQUIRE_RESERVES"] = "1"
    os.environ["AM_VALIDATOR_SELF_REFRESH"] = "1"
    # Seed emissions and prices without reserves initially
    _write_emissions_report(tmp_path, [1])
    _write_price_report(tmp_path, {1: 1.0}, with_reserves=False)

    # Monkeypatch read_prices_items_from_btcli to return reserves
    from subnet.tao20 import price_feed as pf
    def fake_read_items(btcli: str, network: str = "finney", timeout_sec: int = 15):
        from subnet.tao20.reports import PriceItem
        return [PriceItem(uid=1, token="SN1", price_in_tao=1.0, pool_reserve_token="1000", pool_reserve_tao="1000")]
    monkeypatch.setattr(pf, "read_prices_items_from_btcli", fake_read_items)

    client = TestClient(app)
    r = client.post("/mint-tao", headers={"Authorization": "Bearer dev"}, json={"in_dir": str(tmp_path), "amount_tao": 1.0})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"


def test_mint_in_kind_refresh_parity(tmp_path: Path, monkeypatch):
    os.environ["AM_API_TOKEN"] = "dev"
    os.environ["AM_OUT_DIR"] = str(tmp_path)
    # Seed emissions and prices without reserves
    _write_emissions_report(tmp_path, [1])
    _write_price_report(tmp_path, {1: 1.0}, with_reserves=False)
    # Mirror staleness/refresh: reuse existing path that already checks staleness in mint-in-kind logic
    # Provide a perfect basket to pass deviation
    client = TestClient(app)
    # First with refresh disabled and stale price -> allow path still enforces staleness; so enable refresh to be safe
    os.environ["AM_VALIDATOR_SELF_REFRESH"] = "1"
    from subnet.tao20 import price_feed as pf
    def fake_items(btcli: str, network: str = "finney", timeout_sec: int = 15):
        from subnet.tao20.reports import PriceItem
        return [PriceItem(uid=1, token="SN1", price_in_tao=1.0, pool_reserve_token="1000", pool_reserve_tao="1000")]
    monkeypatch.setattr(pf, "read_prices_items_from_btcli", fake_items)
    basket = {"1": 10.0}
    r = client.post("/mint-in-kind", headers={"Authorization": "Bearer dev"}, json={"in_dir": str(tmp_path), "basket": basket})
    assert r.status_code == 200
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
    initial_tx_fees = state.fees_tx_tao
    state = apply_mint_with_tao(100.0, weights={1: 0.5, 2: 0.5}, prices=prices, state=state, fee_bps=20)
    assert state.fees_tx_tao == initial_tx_fees + 0.2
    
    # In-kind mint
    initial_tx_fees = state.fees_tx_tao
    state = apply_mint_in_kind({1: 10.0}, prices, state, fee_bps=20)
    assert state.fees_tx_tao > initial_tx_fees  # Fee is based on value, so it won't be exactly 0.2
    
    # Apply 30-day mgmt fee
    pre_supply = state.tao20_supply
    initial_mgmt_fees = state.fees_mgmt_tao
    state.last_mgmt_ts = "2025-01-01T00:00:00Z"
    state = apply_management_fee(prices, state, now_iso_ts="2025-01-31T00:00:00Z")
    assert state.tao20_supply > pre_supply
    assert state.fees_mgmt_tao > initial_mgmt_fees


def test_mint_with_invalid_amount(tmp_path: Path):
    prices = {1: 2.0, 2: 1.0}
    state = VaultState(holdings={1: 0.0, 2: 0.0}, tao20_supply=100.0, last_nav_tao=1.0)
    
    # Test with zero amount
    state_after_zero_mint = apply_mint_with_tao(0.0, weights={1: 0.5, 2: 0.5}, prices=prices, state=state)
    assert state_after_zero_mint.tao20_supply == state.tao20_supply

    # Test with negative amount
    state_after_negative_mint = apply_mint_with_tao(-100.0, weights={1: 0.5, 2: 0.5}, prices=prices, state=state)
    assert state_after_negative_mint.tao20_supply == state.tao20_supply

def _skip(reason: str):
    import pytest as _pytest
    _pytest.skip(reason)


def test_pr1_signed_reports_skeleton():
    _skip("PR1: add signed EmissionsReport/PriceReport tests")


def test_pr1_validator_quorum_and_slashing_skeleton():
    _skip("PR1: add validator quorum and slashing tests")


def test_pr2_weightset_sha256_stability_skeleton():
    _skip("PR2: add sha256 determinism tests for WeightSet")


def test_pr3_vault_slippage_and_nav_skeleton():
    _skip("PR3: add TAO mint slippage and NAV issuance tests")


