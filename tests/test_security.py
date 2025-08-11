from fastapi.testclient import TestClient
from subnet.validator.api import app
import os
from pathlib import Path
import time
from subnet.tao20.models import EmissionsReport
from subnet.tao20.reports import PriceReport


def test_unauth_post_returns_401(monkeypatch):
    client = TestClient(app)
    # Ensure AM_API_TOKEN is unset; still must require Bearer header
    monkeypatch.delenv("AM_API_TOKEN", raising=False)
    r = client.post("/aggregate", json={"in_dir": "/tmp", "out_file": "/tmp/x", "top_n": 20})
    assert r.status_code == 401


def test_cors_allowed_origin_header(monkeypatch):
    # Configure single allowed origin
    monkeypatch.setenv("AM_CORS_ORIGINS", "https://example.com")
    client = TestClient(app)
    r = client.options("/healthz", headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"})
    # Starlette/fastapi will include access-control-allow-origin when CORS is set
    assert r.headers.get("access-control-allow-origin") == "https://example.com"


def _ts(days_ago: int = 0) -> str:
    t = int(time.time()) - days_ago * 24 * 3600
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def test_hmac_reject_flag(tmp_path: Path, monkeypatch):
    # Prepare HMAC-like reports (signature present but no signer_ss58)
    os.environ["AM_REJECT_HMAC"] = "1"
    os.environ["AM_OUT_DIR"] = str(tmp_path)
    now = _ts(0)
    e = EmissionsReport(snapshot_ts=now, emissions_by_netuid={1: 1.0}, miner_id="m1", stake_tao=1.0, signature="deadbeef")
    (tmp_path / f"emissions_{int(time.time())}_m1.json").write_text(e.to_json(), encoding="utf-8")
    p = PriceReport(ts=now, prices_by_netuid={1: 1.0}, miner_id="m1", signature="deadbeef")
    (tmp_path / f"prices_{int(time.time())}_m1.json").write_text(p.to_json(), encoding="utf-8")
    # Aggregation should exclude these when AM_REJECT_HMAC=1
    from subnet.validator.service import load_reports, load_price_reports
    assert load_reports(tmp_path) == []
    assert load_price_reports(tmp_path) == []


def test_hmac_accept_default(tmp_path: Path, monkeypatch):
    # Default behavior accepts HMAC/unsigned-signer but logs warn
    os.environ.pop("AM_REJECT_HMAC", None)
    os.environ["AM_OUT_DIR"] = str(tmp_path)
    now = _ts(0)
    e = EmissionsReport(snapshot_ts=now, emissions_by_netuid={1: 1.0}, miner_id="m1", stake_tao=1.0, signature="deadbeef")
    (tmp_path / f"emissions_{int(time.time())}_m1.json").write_text(e.to_json(), encoding="utf-8")
    p = PriceReport(ts=now, prices_by_netuid={1: 1.0}, miner_id="m1", signature="deadbeef")
    (tmp_path / f"prices_{int(time.time())}_m1.json").write_text(p.to_json(), encoding="utf-8")
    from subnet.validator.service import load_reports, load_price_reports
    assert len(load_reports(tmp_path)) == 1
    assert len(load_price_reports(tmp_path)) == 1


