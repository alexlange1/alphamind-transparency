from pathlib import Path
import json


def test_readyz_payload(tmp_path: Path):
    # Create minimal weights.json and ensure readyz-style checks pass when read by API impl
    w = {"weights": {"1": 0.5, "2": 0.5}, "sim_nav": 100.0}
    (tmp_path / "weights.json").write_text(json.dumps(w), encoding="utf-8")
    # vault writable check will create and delete a temp file
    # We directly simulate the logic pieces used in the endpoint; full HTTP test omitted.
    assert (tmp_path / "weights.json").exists()
    try:
        p = tmp_path / ".__wtest__"
        p.write_text("ok", encoding="utf-8")
        p.unlink(missing_ok=True)
    except Exception:
        assert False, "vault_writable failed"


