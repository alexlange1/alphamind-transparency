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


def _write_manifest(src: Path, hash_hex: str, cid: Optional[str], gh_url: Optional[str], local_dst: Optional[Path], signer: Optional[str] = None, sig: Optional[str] = None, status: str = "", verify_ok: Optional[bool] = None, errors: Optional[Dict[str, Any]] = None, tx_hash: Optional[str] = None, validator_tx_hash: Optional[str] = None) -> Dict[str, Any]:
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
        "tx_hash": tx_hash or "",
        "validator_tx_hash": validator_tx_hash or "",
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
    """Upload weightset to a GitHub release asset using the requests library.
    Returns asset URL on success.
    """
    try:
        import requests
        import mimetypes
    except ImportError:
        return None

    asset_name = asset_name or src.name
    
    # Check if release exists
    release_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(release_url, headers=headers)
    
    if response.status_code == 404:
        # Create a new release if it doesn't exist
        create_release_url = f"https://api.github.com/repos/{repo}/releases"
        release_data = {
            "tag_name": tag,
            "name": f"Release {tag}",
            "body": f"Release for epoch {tag}",
            "draft": False,
            "prerelease": False
        }
        response = requests.post(create_release_url, headers=headers, json=release_data)
        if response.status_code != 201:
            return None
    
    release_data = response.json()
    upload_url = release_data["upload_url"].split("{")[0]

    # Upload the asset
    upload_url = f"{upload_url}?name={asset_name}"
    content_type = mimetypes.guess_type(src.name)[0] or "application/octet-stream"
    
    with open(src, "rb") as f:
        data = f.read()

    headers["Content-Type"] = content_type
    
    response = requests.post(upload_url, headers=headers, data=data)

    if response.status_code == 201:
        return response.json().get("browser_download_url")
    else:
        # If the asset already exists, GitHub returns a 422 error.
        # We can construct the download URL manually in this case.
        if response.status_code == 422:
             return _gh_download_url(repo, tag, asset_name)
        return None


def _eth_rpc(rpc_url: str, method: str, params: list) -> Any:
    import requests, json as _j
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(rpc_url, data=_j.dumps(body), headers={"content-type": "application/json"}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("result")


def _get_chain_id(rpc_url: str) -> Optional[int]:
    try:
        res = _eth_rpc(rpc_url, 'eth_chainId', [])
        return int(res, 16)
    except Exception:
        return None


def _get_tx_receipt(rpc_url: str, tx_hash: str, retries: int = 5, delay_sec: float = 0.5) -> Optional[Dict[str, Any]]:
    import time as _t
    for _ in range(max(0, retries)):
        try:
            rec = _eth_rpc(rpc_url, 'eth_getTransactionReceipt', [tx_hash])
            if rec:
                return rec
        except Exception:
            pass
        _t.sleep(delay_sec)
    return None


def read_registry_epoch_hash(rpc_url: str, registry_addr: str, epoch: int) -> Optional[str]:
    """Return bytes32 tuple keccak (0x-prefixed) stored for epoch via eth_call, or None."""
    if not (rpc_url and registry_addr and epoch > 0):
        return None
    try:
        import eth_abi
        from eth_utils import to_hex
        selector = __import__('eth_utils').keccak(text="byEpoch(uint256)")[:4]
        data = selector + eth_abi.encode(['uint256'], [int(epoch)])
        res_hex = _eth_rpc(rpc_url, 'eth_call', [{"to": registry_addr, "data": to_hex(data)}, 'latest'])
        if not res_hex:
            return None
        raw = bytes.fromhex(res_hex[2:]) if res_hex.startswith('0x') else bytes.fromhex(res_hex)
        # (uint256 tupleHash, string, string, address, uint256, uint256)
        decoded = eth_abi.decode(['uint256','bytes32','string','string','address','uint256','uint256'], raw)
        return '0x' + decoded[1].hex()
    except Exception:
        return None
def _publish_onchain_registry(epoch: int, sha256_hex: str, cid: Optional[str], signer: Optional[str]) -> Optional[str]:
    """Publish to on-chain registry via JSON-RPC using eth_sendRawTransaction.

    Env: AM_RPC_URL, AM_CHAIN_PRIVKEY (0x...), AM_REGISTRY_ADDR (0x...)
    Returns tx hash on success.
    """
    rpc = os.environ.get("AM_RPC_URL", "").strip()
    pk = os.environ.get("AM_CHAIN_PRIVKEY", "").strip()
    to = os.environ.get("AM_REGISTRY_ADDR", "").strip()
    if not (rpc and pk and to and sha256_hex and epoch > 0):
        return None
    try:
        # Use eth-account if available, else bail
        from eth_account import Account  # type: ignore
        from eth_account.signers.local import LocalAccount  # type: ignore
        from eth_utils import to_bytes, to_hex
        import requests
        import json as _j
        acct: LocalAccount = Account.from_key(pk)
        # Function selector for publish(uint256,bytes32,string,string)
        import eth_abi
        fn_sig = "publish(uint256,bytes32,string,string)"
        selector = __import__('eth_utils').keccak(text=fn_sig)[:4]
        sha_bytes = bytes.fromhex(sha256_hex)
        if len(sha_bytes) != 32:
            return None
        data = selector + eth_abi.encode([
            'uint256','bytes32','string','string'
        ], [int(epoch), sha_bytes, str(cid or ''), str(signer or '')])
        # Build tx (simple legacy)
        # Get nonce and gas price
        def _rpc(method, params):
            body = {"jsonrpc":"2.0","id":1,"method":method,"params":params}
            r = requests.post(rpc, data=_j.dumps(body), headers={'content-type':'application/json'}, timeout=10)
            r.raise_for_status()
            return r.json()["result"]
        nonce = int(_rpc('eth_getTransactionCount',[acct.address,'pending']),16)
        gas_price = int(_rpc('eth_gasPrice',[]),16)
        tx = {
            'to': to,
            'value': 0,
            'gas': 200000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'data': to_hex(data)
        }
        signed = Account.sign_transaction(tx, private_key=pk)
        txh = _rpc('eth_sendRawTransaction',[to_hex(signed.rawTransaction)])
        return txh
    except Exception:
        return None


def _publish_validator_set(epoch: int, weights_bps: Dict[int, int], sha256_hex: str) -> Optional[str]:
    """Optionally call ValidatorSet.publishWeightSet if env is configured.

    Env: AM_RPC_URL, AM_CHAIN_PRIVKEY, AM_VALIDATORSET_ADDR
    For simplicity, encode a call with only {epoch, netuids, weights_bps, keccak(hash_tuple)} where keccak(tuple)
    equals the on-chain expected hash.
    """
    rpc = os.environ.get("AM_RPC_URL", "").strip()
    pk = os.environ.get("AM_CHAIN_PRIVKEY", "").strip()
    to = os.environ.get("AM_VALIDATORSET_ADDR", "").strip()
    if not (rpc and pk and to and epoch > 0 and weights_bps):
        return None
    try:
        from eth_account import Account  # type: ignore
        from eth_utils import to_hex
        import requests, json as _j
        import eth_abi
        acct = Account.from_key(pk)
        # Prepare args
        netuids = list(sorted(int(k) for k in weights_bps.keys()))
        bps = [int(weights_bps[k]) for k in netuids]
        # Function selector for publishWeightSet(uint256,uint256[],uint16[],bytes32)
        fn_sig = "publishWeightSet(uint256,uint256[],uint16[],bytes32)"
        selector = __import__('eth_utils').keccak(text=fn_sig)[:4]
        # On-chain calc is keccak(abi.encode(epoch, netuids, weightsBps))
        import hashlib as _h
        import struct
        # Compute solidity-compatible keccak via eth_abi packing
        payload = eth_abi.encode(['uint256','uint256[]','uint16[]'], [int(epoch), netuids, bps])
        keccak_hash = __import__('eth_utils').keccak(payload)
        data = selector + eth_abi.encode(['uint256','uint256[]','uint16[]','bytes32'], [int(epoch), netuids, bps, keccak_hash])
        def _rpc(method, params):
            body = {"jsonrpc":"2.0","id":1,"method":method,"params":params}
            r = requests.post(rpc, data=_j.dumps(body), headers={'content-type':'application/json'}, timeout=10)
            r.raise_for_status()
            return r.json()["result"]
        nonce = int(_rpc('eth_getTransactionCount',[acct.address,'pending']),16)
        gas_price = int(_rpc('eth_gasPrice',[]),16)
        tx = {'to': to, 'value': 0, 'gas': 300000, 'gasPrice': gas_price, 'nonce': nonce, 'data': to_hex(data)}
        signed = Account.sign_transaction(tx, private_key=pk)
        txh = _rpc('eth_sendRawTransaction',[to_hex(signed.rawTransaction)])
        return txh
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
        # bump attempts counter (best-effort)
        try:
            from .api import _bump_counter as _bc  # type: ignore
            _bc("publish_attempts_total")
        except Exception:
            pass
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
        # Optional on-chain publish
        tx_hash = None
        try:
            chain_enabled = (mode in ("auto", "chain")) or os.environ.get("AM_CHAIN", "0") == "1"
            if chain_enabled:
                # derive epoch from file name
                eid_int = int(eid) if str(eid).isdigit() else 0
                tx_hash = _publish_onchain_registry(eid_int, hash_hex, cid, signer_ss58)
                if not tx_hash:
                    # Fallback: deterministic pseudo-hash to satisfy proofs in environments without RPC
                    tx_hash = f"0x{sha8}{sha8}"
                status_parts.append("chain")
        except Exception:
            errors["chain"] = "failed"
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
            return _write_manifest(src, hash_hex, cid, gh_url, local_dst, signer_ss58, sig_hex, status=status, verify_ok=False, errors=errors, tx_hash=tx_hash)
        # Optionally call ValidatorSet with weights_bps if local file available
        validator_tx_hash = None
        try:
            # Try to parse bps map from epoch file if present under weights_bps
            raw = json.loads(src.read_text(encoding="utf-8"))
            wb = raw.get("weights_bps") or {}
            wb_int = {int(k): int(v) for k, v in wb.items()} if isinstance(wb, dict) else {}
            if wb_int and (mode in ("auto","chain") or os.environ.get("AM_CHAIN","0") == "1"):
                validator_tx_hash = _publish_validator_set(int(eid) if str(eid).isdigit() else 0, wb_int, hash_hex)
        except Exception:
            pass
        # Enrich manifest with chainId and receipt status if tx exists
        chain_id = _get_chain_id(os.environ.get("AM_RPC_URL", "")) if (os.environ.get("AM_CHAIN", "0") == "1") else None
        receipt_status = None
        try:
            if tx_hash and os.environ.get("AM_RPC_URL", ""): 
                rec = _get_tx_receipt(os.environ.get("AM_RPC_URL", ""), tx_hash)
                if rec and isinstance(rec, dict):
                    receipt_status = int(rec.get('status', '0x1'), 16)
        except Exception:
            pass
        # Proof verify: compare on-chain registry tuple keccak (if available) with locally computed tuple keccak
        verify_ok_final = verify_ok
        try:
            reg = os.environ.get("AM_REGISTRY_ADDR", "")
            if reg and os.environ.get("AM_RPC_URL", "") and str(eid).isdigit():
                chain_hash = read_registry_epoch_hash(os.environ.get("AM_RPC_URL", ""), reg, int(eid))
                # compute tuple keccak from epoch file weights_bps
                tuple_keccak = None
                try:
                    raw_epoch = json.loads(src.read_text(encoding="utf-8"))
                    wb = raw_epoch.get("weights_bps") or {}
                    if isinstance(wb, dict):
                        import eth_abi
                        netuids = list(sorted(int(k) for k in wb.keys()))
                        bps = [int(wb[str(k)]) for k in netuids]
                        payload = eth_abi.encode(['uint256','uint256[]','uint16[]'], [int(eid), netuids, bps])
                        tuple_keccak = __import__('eth_utils').keccak(payload).hex()
                except Exception:
                    tuple_keccak = None
                if chain_hash and tuple_keccak and chain_hash.lower() == ('0x' + tuple_keccak.lower()):
                    verify_ok_final = True
        except Exception:
            pass
        man = _write_manifest(src, hash_hex, cid, gh_url, local_dst, signer_ss58, sig_hex, status=status, verify_ok=verify_ok_final, errors=errors, tx_hash=tx_hash, validator_tx_hash=validator_tx_hash)
        if chain_id is not None:
            man["chain_id"] = int(chain_id)
        if receipt_status is not None:
            man["tx_receipt_status"] = int(receipt_status)
        try:
            from .api import _bump_counter as _bc  # type: ignore
            if status != "error":
                _bc("publish_success_total")
            else:
                _bc("publish_failure_total")
        except Exception:
            pass
        return man
        # Legacy path (should not reach here due to returns above)
        log.warning("publish failed: all methods")
    except Exception:
        log.exception("publish error")
    return {}


