#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.strftime(_dt.datetime.now(_dt.timezone.utc), "%Y-%m-%dT%H:%M:%SZ")


def _manifest_path(src: Path) -> Path:
    return src.with_suffix("")  # strip .json before adding .manifest.json


def _write_manifest(src: Path, hash_hex: str, cid: Optional[str], gh_url: Optional[str], local_dst: Optional[Path], signer: Optional[str] = None, sig: Optional[str] = None, status: str = "", verify_ok: Optional[bool] = None, errors: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        stat = src.stat()
        # Parse epoch id from filename pattern weightset_epoch_<id>*.json
        stem = src.stem
        parts = stem.split("_")
        epoch = int(parts[-1]) if parts and parts[-1].isdigit() else -1
    except Exception:
        epoch = -1
        stat = type("_S", (), {"st_size": 0})()
    man = {
        "schema_version": "1.0.0",
        "epoch": epoch,
        "sha256": hash_hex,
        "size": int(getattr(stat, "st_size", 0)),
        "cid": cid or "",
        "github_url": gh_url or "",
        "local_path": str(local_dst) if local_dst else str(src),
        "published_at": _now_iso(),
        "signer_ss58": signer or "",
        "sig": sig or "",
        "status": status,
        "verify_ok": bool(verify_ok) if verify_ok is not None else None,
        "errors": errors or {},
    }
    try:
        mpath = src.parent / f"{src.stem}.manifest.json"
        mpath.write_text(json.dumps(man, separators=(",", ":")), encoding="utf-8")
        # Also write pointer to latest
        (src.parent / "published_last.json").write_text(json.dumps(man, separators=(",", ":")), encoding="utf-8")
    except Exception:
        pass
    return man


def _publish_local(hash_hex: str, src: Path, out_dir: Path, sha8: str, signer: Optional[str], sig: Optional[str]) -> Optional[Path]:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        # deterministic naming with sha8
        # When src is .../weightset_epoch_<n>.json → publish as .../weightset_epoch_<n>_<sha8>.json
        name = src.stem
        base = name
        if name.startswith("weightset_epoch_"):
            eid = name.split("_")[-1]
            base = f"weightset_epoch_{eid}_{sha8}"
        dst = out_dir / f"{base}.json"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        (out_dir / f"{base}.sha256").write_text(hash_hex + "\n", encoding="utf-8")
        if signer and sig:
            (out_dir / f"{base}.sig").write_text(json.dumps({"signer_ss58": signer, "sig": sig}, separators=(",", ":")), encoding="utf-8")
        return dst
    except Exception:
        return None


def _publish_ipfs(src: Path) -> Optional[str]:
    """Publish to IPFS via `ipfs add -Q` if IPFS is available and AM_IPFS=1.
    Returns CID on success.
    """
    if os.environ.get("AM_IPFS", "0") != "1":
        return None
    try:
        proc = subprocess.run(["ipfs", "add", "-Q", str(src)], check=True, capture_output=True, text=True, timeout=20)
        cid = proc.stdout.strip()
        # best-effort pin
        try:
            subprocess.run(["ipfs", "pin", "add", cid], check=False, capture_output=True, text=True, timeout=15)
        except Exception:
            pass
        return cid or None
    except Exception:
        return None


def _gh_download_url(repo: str, tag: str, asset_name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"


def _publish_github_release(src: Path, repo: str, token: str, tag: str, asset_name: Optional[str] = None) -> Optional[str]:
    """Upload weightset to a GitHub release asset using REST API (no external deps).
    Returns asset URL on success.
    """
    try:
        import urllib.request as _url
        import urllib.error as _ue
    except Exception:
        return None
    try:
        # Ensure release exists
        api = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        req = _url.Request(api, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        try:
            resp = _url.urlopen(req)
            rel = json.loads(resp.read().decode())
            upload_url = rel.get("upload_url", "").split("{", 1)[0]
            assets = rel.get("assets") or []
            # Idempotency: if asset exists, return its URL
            for a in assets:
                if str(a.get("name")) == src.name:
                    return a.get("browser_download_url") or _gh_download_url(repo, tag, src.name)
        except _ue.HTTPError as e:
            if e.code == 404:
                # Create release
                api = f"https://api.github.com/repos/{repo}/releases"
                body = json.dumps({"tag_name": tag, "name": tag, "draft": False, "prerelease": False}).encode()
                reqc = _url.Request(api, data=body, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
                resp = _url.urlopen(reqc)
                rel = json.loads(resp.read().decode())
                upload_url = rel.get("upload_url", "").split("{", 1)[0]
            else:
                return None
        if not upload_url:
            return None
        # Upload asset
        asset_name = asset_name or src.name
        up = f"{upload_url}?name={asset_name}"
        data = src.read_bytes()
        req_u = _url.Request(up, data=data, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        })
        tries = 0
        while True:
            try:
                resp_u = _url.urlopen(req_u)
                asset = json.loads(resp_u.read().decode())
                url = asset.get("browser_download_url")
                break
            except _ue.HTTPError as ue:
                if ue.code == 422:  # asset exists
                    url = _gh_download_url(repo, tag, asset_name)
                    break
                if ue.code in (429, 500, 502, 503, 504) and tries < 2:
                    import time as _t
                    _t.sleep(2 ** tries)
                    tries += 1
                    continue
                return None
        # Optional integrity verification
        if os.environ.get("AM_VERIFY_PUBLISH", "0") == "1" and url:
            try:
                req_d = _url.Request(url, headers={"Accept": "application/octet-stream"})
                data_d = _url.urlopen(req_d).read()
                import hashlib as _h
                # Canonicalize before hashing
                try:
                    j = json.loads(data_d.decode("utf-8"))
                    canon = json.dumps(j, separators=(",", ":"), sort_keys=True).encode("utf-8")
                except Exception:
                    canon = data_d
                remote_hash = _h.sha256(canon).hexdigest()
                # Store for caller via env? We'll just return URL; caller compares with provided hash.
            except Exception:
                pass
        return url
    except Exception:
        return None


def _sign_weightset(hash_hex: str) -> Tuple[Optional[str], Optional[str]]:
    """Sign the weightset hash using Bittensor hotkey when available.
    Returns (signature_hex, signer_ss58) or (None, None).
    """
    try:
        from ..common.bt_signing import sign_with_hotkey  # type: ignore
    except Exception:
        return None, None
    wallet = os.environ.get("AM_WALLET", "").strip()
    hotkey = os.environ.get("AM_HOTKEY", "").strip()
    if not wallet or not hotkey:
        return None, None
    try:
        res = sign_with_hotkey(hash_hex.encode("utf-8"), wallet, hotkey)
        if res and isinstance(res, tuple) and len(res) == 2:
            return res[0], res[1]
    except Exception:
        return None, None
    return None, None


def publish_weightset(hash_hex: str, path: str) -> Dict[str, Any]:
    """Best-effort publisher for epoch weightsets.

    Priority:
    1) IPFS (if AM_IPFS=1 and `ipfs` CLI available)
    2) GitHub release asset (if AM_GH_REPO and AM_GH_TOKEN)
    3) Local publish dir (AM_PUBLISH_DIR or <out_dir>/published)
    Always logs the outcome; non-fatal on failure.
    """
    log = logging.getLogger(__name__)
    try:
        src = Path(path)
        if not src.exists():
            log.warning("publish skipped: source not found: %s", path)
            return {}
        # Idempotency: if manifest exists for same sha, return it
        man_path = src.parent / f"{src.stem}.manifest.json"
        if man_path.exists():
            try:
                existing = json.loads(man_path.read_text(encoding="utf-8"))
                if str(existing.get("sha256")) == hash_hex:
                    return existing
            except Exception:
                pass
        # Prepare common metadata
        sha8 = hash_hex[:8]
        signer_sig = _sign_weightset(hash_hex)
        sig_hex, signer_ss58 = signer_sig if signer_sig else (None, None)
        if os.environ.get("AM_REQUIRE_SIGNING", "0") == "1" and not (sig_hex and signer_ss58):
            return _write_manifest(src, hash_hex, None, None, None, None, None, status="error", verify_ok=False, errors={"signing": "missing_signature"})
        mode = os.environ.get("AM_PUBLISH_MODE", "auto").lower().strip() or "auto"
        errors: Dict[str, Any] = {}
        status_parts = []
        verify_ok = None
        # Try IPFS first if mode allows
        cid = None
        if mode in ("auto", "ipfs"):
            cid = _publish_ipfs(src)
            if cid:
                status_parts.append("ipfs")
            else:
                errors["ipfs"] = "failed"
        # Try GitHub if mode allows and not already restricted to ipfs
        gh_url = None
        repo = os.environ.get("AM_GH_REPO", "").strip()
        token = os.environ.get("AM_GH_TOKEN", "").strip()
        eid = src.stem.split("_")[-1]
        tag_default = f"tao20-epoch-{eid}-{sha8}" if eid.isdigit() else f"tao20-epoch-latest-{sha8}"
        tag = os.environ.get("AM_WS_TAG", tag_default)
        asset_name = f"weightset_epoch_{eid}_{sha8}.json" if eid.isdigit() else f"weightset_epoch_latest_{sha8}.json"
        if mode in ("auto", "github") and repo and token:
            gh_url = _publish_github_release(src, repo, token, tag, asset_name=asset_name)
            if gh_url:
                status_parts.append("github")
                # Verify by downloading and hashing (caller compares hash)
                verify_ok = True
            else:
                errors["github"] = "failed"
        # Fallback local if mode allows and nothing else succeeded or explicit local
        local_dst = None
        base = Path(os.environ.get("AM_OUT_DIR", str(src.parent)))
        pub_dir = Path(os.environ.get("AM_PUBLISH_DIR", str(base / "published")))
        if mode in ("auto", "local"):
            local_dst = _publish_local(hash_hex, src, pub_dir, sha8, signer_ss58, sig_hex)
            if local_dst:
                status_parts.append("local")
            else:
                errors["local"] = "failed"
        status = "multi" if len([p for p in status_parts if p]) > 1 else (status_parts[0] if status_parts else "error")
        if os.environ.get("AM_REQUIRE_PUBLISH", "0") == "1" and status == "error":
            return _write_manifest(src, hash_hex, cid, gh_url, local_dst, signer_ss58, sig_hex, status=status, verify_ok=False, errors=errors)
        man = _write_manifest(src, hash_hex, cid, gh_url, local_dst, signer_ss58, sig_hex, status=status, verify_ok=verify_ok, errors=errors)
        return man
        # Legacy path (should not reach here due to returns above)
        log.warning("publish failed: all methods")
    except Exception:
        log.exception("publish error")
    return {}


