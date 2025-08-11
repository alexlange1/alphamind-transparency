import json
import time
from pathlib import Path

import pytest

from subnet.validator.publish import publish_weightset


@pytest.mark.parametrize("mode", ["chain", "auto"]) 
def test_publish_onchain_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str):
    ws = {"epoch_id": 2, "as_of_ts": "2025-01-01T00:00:00Z", "weights": {"1": 0.5, "2": 0.5}}
    p = tmp_path / "weightset_epoch_2.json"
    p.write_text(json.dumps(ws, separators=(",", ":")), encoding="utf-8")
    import hashlib
    sha = hashlib.sha256(json.dumps(ws, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()

    # Set chain env
    monkeypatch.setenv("AM_PUBLISH_MODE", mode)
    monkeypatch.setenv("AM_CHAIN", "1")
    monkeypatch.setenv("AM_RPC_URL", "http://localhost:8545")
    monkeypatch.setenv("AM_CHAIN_PRIVKEY", "0x" + "11"*32)
    monkeypatch.setenv("AM_REGISTRY_ADDR", "0x" + "22"*20)

    # Mock RPC and signing
    calls = {"sent": False}
    class _Resp:
        def __init__(self, result):
            self._result = result
        def raise_for_status(self):
            return None
        def json(self):
            return {"jsonrpc":"2.0","id":1,"result": self._result}
    def fake_post(url, data=None, headers=None, timeout=None):
        body = json.loads(data)
        if body["method"] == "eth_getTransactionCount":
            return _Resp("0x0")
        if body["method"] == "eth_gasPrice":
            return _Resp("0x3b9aca00")  # 1 gwei
        if body["method"] == "eth_sendRawTransaction":
            calls["sent"] = True
            return _Resp("0xdeadbeef")
        return _Resp("0x0")
    monkeypatch.setattr("requests.post", fake_post)

    man = publish_weightset(sha, str(p))
    assert man.get("sha256") == sha
    assert calls["sent"] is True
    assert man.get("tx_hash") == "0xdeadbeef"
    # Receipt fields may be None in mock; chain_id absent. Ensure manifest present and stable fields exist
    assert "epoch" in man


