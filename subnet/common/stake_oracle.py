#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple, Optional
import time
import hmac
import hashlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def verify_stake_file(file_path: Path, secret: str) -> bool:
    """Verify the HMAC signature of the stake file."""
    signature_path = file_path.with_suffix(".sig")
    if not signature_path.exists():
        logging.warning(f"Signature file not found for stake oracle at {file_path}")
        return False

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        with open(signature_path, "r") as f:
            signature = f.read().strip()

        expected_signature = hmac.new(secret.encode(), file_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except IOError as e:
        logging.error(f"Error reading stake file or signature: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during stake file verification: {e}")
        return False


def load_stake_oracle() -> Tuple[Dict[str, float], Optional[float]]:
    """Load miner stake weights from a signed JSON file.

    Env:
      - AM_STAKE_ORACLE_JSON: path to JSON file containing {"miners": {"<miner_id>": <stake>...}, "ts": "ISO8601Z" or epoch}
      - AM_STAKE_ORACLE_SECRET: secret for HMAC verification
    Returns:
      (stake_by_miner, age_sec) where age_sec is seconds since oracle timestamp if present, else None.
    """
    path_str = os.environ.get("AM_STAKE_ORACLE_JSON", "").strip()
    secret = os.environ.get("AM_STAKE_ORACLE_SECRET", "").strip()
    
    if not path_str or not secret:
        logging.warning("Stake oracle path or secret not configured. Skipping.")
        return {}, None
        
    path = Path(path_str)
    if not path.exists():
        logging.warning(f"Stake oracle file not found at {path}")
        return {}, None

    if not verify_stake_file(path, secret):
        logging.error("Stake oracle file verification failed. Discarding.")
        return {}, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        miners = raw.get("miners") or raw.get("stakes") or {}
        stake_by_miner: Dict[str, float] = {}
        for k, v in miners.items():
            try:
                stake_by_miner[str(k)] = float(v)
            except Exception:
                continue
        # Timestamp handling
        ts = raw.get("ts") or raw.get("timestamp")
        age_sec: Optional[float] = None
        if ts is not None:
            try:
                if isinstance(ts, (int, float)):
                    age_sec = max(0.0, time.time() - float(ts))
                else:
                    import datetime as _dt
                    if isinstance(ts, str):
                        # Accept ISO8601Z
                        if ts.endswith("Z"):
                            dt = _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
                        else:
                            # Best-effort parse
                            dt = _dt.datetime.fromisoformat(ts)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=_dt.timezone.utc)
                        age_sec = max(0.0, time.time() - dt.timestamp())
            except Exception:
                age_sec = None
        return stake_by_miner, age_sec
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from stake oracle file: {e}")
        return {}, None
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading stake oracle: {e}")
        return {}, None


