#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional


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
        resp_u = _url.urlopen(req_u)
        asset = json.loads(resp_u.read().decode())
        return asset.get("browser_download_url")
    except Exception:
        return None


def publish_weightset(hash_hex: str, path: str) -> None:
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
            return
        # Try IPFS
        cid = _publish_ipfs(src)
        if cid:
            log.info("publish ipfs ok: cid=%s path=%s", cid, path)
            return
        # Try GitHub
        repo = os.environ.get("AM_GH_REPO", "").strip()  # e.g., alexlange1/alphamind
        token = os.environ.get("AM_GH_TOKEN", "").strip()
        tag = os.environ.get("AM_WS_TAG", f"weightset-epoch-{src.stem.split('_')[-1] if '_' in src.stem else 'latest'}")
        if repo and token:
            url = _publish_github_release(src, repo, token, tag)
            if url:
                log.info("publish github ok: url=%s path=%s", url, path)
                return
        # Fallback local
        base = Path(os.environ.get("AM_OUT_DIR", str(src.parent)))
        pub_dir = Path(os.environ.get("AM_PUBLISH_DIR", str(base / "published")))
        dst = _publish_local(hash_hex, src, pub_dir)
        if dst:
            log.info("publish local ok: %s", str(dst))
        else:
            log.warning("publish failed: all methods")
    except Exception:
        log.exception("publish error")


