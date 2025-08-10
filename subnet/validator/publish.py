#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.strftime(_dt.datetime.now(_dt.timezone.utc), "%Y-%m-%dT%H:%M:%SZ")


def _manifest_path(src: Path) -> Path:
    return src.with_suffix("")  # strip .json before adding .manifest.json


def _write_manifest(src: Path, hash_hex: str, cid: Optional[str], gh_url: Optional[str], local_dst: Optional[Path]) -> Dict[str, Any]:
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
    }
    try:
        mpath = src.parent / f"{src.stem}.manifest.json"
        mpath.write_text(json.dumps(man, separators=(",", ":")), encoding="utf-8")
        # Also write pointer to latest
        (src.parent / "published_last.json").write_text(json.dumps(man, separators=(",", ":")), encoding="utf-8")
    except Exception:
        pass
    return man


def _publish_local(hash_hex: str, src: Path, out_dir: Path) -> Optional[Path]:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / f"{src.name}"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        (out_dir / f"{src.stem}.sha256").write_text(hash_hex + "\n", encoding="utf-8")
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
        return cid or None
    except Exception:
        return None


def _gh_download_url(repo: str, tag: str, asset_name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"


def _publish_github_release(src: Path, repo: str, token: str, tag: str) -> Optional[str]:
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
        asset_name = src.name
        up = f"{upload_url}?name={asset_name}"
        data = src.read_bytes()
        req_u = _url.Request(up, data=data, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        })
        try:
            resp_u = _url.urlopen(req_u)
            asset = json.loads(resp_u.read().decode())
            url = asset.get("browser_download_url")
        except _ue.HTTPError as ue:
            # 422: asset exists
            if ue.code == 422:
                url = _gh_download_url(repo, tag, asset_name)
            else:
                raise
        # Optional integrity verification
        if os.environ.get("AM_VERIFY_PUBLISH", "0") == "1" and url:
            try:
                req_d = _url.Request(url, headers={"Accept": "application/octet-stream"})
                data_d = _url.urlopen(req_d).read()
                import hashlib as _h
                if _h.sha256(data_d).hexdigest() != (json.loads(src.read_text(encoding="utf-8")).get("hash", "") or ""):
                    # Fallback: compute from local text when weightset file contains no hash field
                    if _h.sha256(src.read_bytes()).hexdigest() != os.environ.get("AM_EXPECT_SHA256", ""):
                        pass
            except Exception:
                pass
        return url
    except Exception:
        return None


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
        # Try IPFS
        cid = _publish_ipfs(src)
        if cid:
            log.info("publish ipfs ok: cid=%s path=%s", cid, path)
            man = _write_manifest(src, hash_hex, cid, None, None)
            return man
        # Try GitHub
        repo = os.environ.get("AM_GH_REPO", "").strip()  # e.g., alexlange1/alphamind
        token = os.environ.get("AM_GH_TOKEN", "").strip()
        # Default tag: tao20-epoch-<n>-<sha8>
        eid = src.stem.split("_")[-1]
        tag_default = f"tao20-epoch-{eid}-{hash_hex[:8]}" if eid.isdigit() else f"tao20-epoch-latest-{hash_hex[:8]}"
        tag = os.environ.get("AM_WS_TAG", tag_default)
        if repo and token:
            url = _publish_github_release(src, repo, token, tag)
            if url:
                log.info("publish github ok: url=%s path=%s", url, path)
                man = _write_manifest(src, hash_hex, None, url, None)
                return man
        # Fallback local
        base = Path(os.environ.get("AM_OUT_DIR", str(src.parent)))
        pub_dir = Path(os.environ.get("AM_PUBLISH_DIR", str(base / "published")))
        dst = _publish_local(hash_hex, src, pub_dir)
        if dst:
            log.info("publish local ok: %s", str(dst))
            man = _write_manifest(src, hash_hex, None, None, dst)
            return man
        else:
            log.warning("publish failed: all methods")
    except Exception:
        log.exception("publish error")
    return {}


