import json
import time
from pathlib import Path

import pytest

from subnet.tao20.models import EmissionsReport
from subnet.tao20.reports import PriceReport, PriceItem
from subnet.common.crypto import sign_message
from subnet.validator import service as vsvc
from subnet.validator.publish import publish_weightset


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def test_hmac_emissions_report_accepts(tmp_path: Path):
    ts = _ts()
    rep = EmissionsReport(
        snapshot_ts=ts,
        emissions_by_netuid={1: 10.0, 2: 20.0},
        miner_id="miner-A",
        stake_tao=100.0,
        schema_version="1.0.0",
    )
    payload = rep.to_json()
    sig = sign_message("secret", payload)
    rep = EmissionsReport.from_json(payload)
    rep = EmissionsReport(
        snapshot_ts=rep.snapshot_ts,
        emissions_by_netuid=rep.emissions_by_netuid,
        miner_id=rep.miner_id,
        stake_tao=rep.stake_tao,
        signature=sig,
        signer_ss58="",
        schema_version="1.0.0",
    )
    p = tmp_path / f"emissions_{int(time.time())}_miner-A.json"
    p.write_text(rep.to_json(), encoding="utf-8")
    reps = vsvc.load_reports(tmp_path)
    assert any(r.miner_id == "miner-A" for r in reps)


def test_hotkey_emissions_report_accepts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ts = _ts()
    rep = EmissionsReport(
        snapshot_ts=ts,
        emissions_by_netuid={1: 10.0},
        miner_id="hotkey-XYZ",
        stake_tao=50.0,
        schema_version="1.0.0",
        signature="deadbeef",
        signer_ss58="5F3sa2TJ...",
    )
    p = tmp_path / f"emissions_{int(time.time())}_hk.json"
    p.write_text(rep.to_json(), encoding="utf-8")

    def _ok(_msg: bytes, _sig: str, _who: str) -> bool:
        return True

    monkeypatch.setattr(vsvc, "verify_with_ss58", _ok)
    reps = vsvc.load_reports(tmp_path)
    assert any(r.signer_ss58 == "5F3sa2TJ..." for r in reps)


def test_bad_sig_emissions_report_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ts = _ts()
    rep = EmissionsReport(
        snapshot_ts=ts,
        emissions_by_netuid={1: 10.0},
        miner_id="hotkey-XYZ",
        stake_tao=50.0,
        schema_version="1.0.0",
        signature="bad",
        signer_ss58="5F3sa2TJ...",
    )
    p = tmp_path / f"emissions_{int(time.time())}_hkbad.json"
    p.write_text(rep.to_json(), encoding="utf-8")

    def _no(_msg: bytes, _sig: str, _who: str) -> bool:
        return False

    monkeypatch.setattr(vsvc, "verify_with_ss58", _no)
    reps = vsvc.load_reports(tmp_path)
    assert all(r.signer_ss58 != "5F3sa2TJ..." for r in reps)


def test_price_report_schema_v1_and_legacy():
    ts = _ts()
    items = [PriceItem(uid=1, token="SN1", price_in_tao=1.23), PriceItem(uid=2, token="SN2", price_in_tao=0.5)]
    pr = PriceReport(ts=ts, prices_by_netuid={1: 1.23, 2: 0.5}, miner_id="M", schema_version="1.0.0", prices=items)
    text = pr.to_json()
    pr2 = PriceReport.from_json(text)
    assert pr2.prices_by_netuid.get(1) == 1.23 and pr2.prices is not None and len(pr2.prices) == 2

    legacy = PriceReport(ts=ts, prices_by_netuid={3: 9.9}, miner_id="L")
    text2 = legacy.to_json()
    pr3 = PriceReport.from_json(text2)
    assert pr3.prices_by_netuid.get(3) == 9.9 and (pr3.prices is None or len(pr3.prices) in (0, None))


def test_publish_manifest_includes_txhash(tmp_path: Path, monkeypatch):
    # Create a dummy weightset file
    ws = {"epoch_id": 1, "as_of_ts": "2025-01-01T00:00:00Z", "weights": {"1": 0.5, "2": 0.5}}
    p = tmp_path / "weightset_epoch_1.json"
    p.write_text(json.dumps(ws, separators=(",", ":")), encoding="utf-8")
    import hashlib
    sha = hashlib.sha256(json.dumps(ws, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()
    monkeypatch.setenv("AM_PUBLISH_MODE", "auto")
    man = publish_weightset(sha, str(p))
    assert man.get("sha256") == sha
    # tx_hash may be empty if chain disabled; enable chain mode
    monkeypatch.setenv("AM_CHAIN", "1")
    # Mock eth_call to satisfy verify path and return deterministic tuple hash equal to local tuple_keccak
    def fake_post(url, data=None, headers=None, timeout=None):
        body = json.loads(data)
        if body["method"] == "eth_getTransactionCount":
            return type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: {"result": "0x0"}})()
        if body["method"] == "eth_gasPrice":
            return type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: {"result": "0x3b9aca00"}})()
        if body["method"] == "eth_sendRawTransaction":
            return type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: {"result": "0xdeadbeef"}})()
        if body["method"] == "eth_call":
            # Return ABI-encoded byEpoch tuple with matching tupleHash
            import eth_abi, eth_utils
            netuids = [1,2]
            bps = [5000,5000]
            payload = eth_abi.encode(['uint256','uint256[]','uint16[]'], [1, netuids, bps])
            th = eth_utils.keccak(payload)
            enc = eth_abi.encode(['uint256','bytes32','string','string','address','uint256','uint256'], [1, th, "", "", "0x0000000000000000000000000000000000000000", 0, 0])
            return type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: {"result": "0x"+enc.hex()}})()
        return type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: {"result": None}})()
    monkeypatch.setenv("AM_RPC_URL", "http://localhost:8545")
    monkeypatch.setenv("AM_REGISTRY_ADDR", "0x"+"11"*20)
    monkeypatch.setenv("AM_CHAIN_PRIVKEY", "0x"+"22"*32)
    import requests as _req
    monkeypatch.setattr(_req, "post", fake_post)
    man2 = publish_weightset(sha, str(p))
    assert man2.get("tx_hash", "").startswith("0x")


