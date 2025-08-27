#!/usr/bin/env python3
from __future__ import annotations

# Standard library imports
import csv
import os
import subprocess
import time
import logging

# Third-party imports
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

# Local imports (alphabetical)
from collections import defaultdict
import datetime
from .common.settings import get_settings

"""Core Data Structures and Exceptions"""

# Fallback protocol constants (used when epoch module is unavailable)
_FALLBACK_EPOCH_ANCHOR_UNIX = 1_723_593_600  # 2024-08-14 00:00:00 UTC
_FALLBACK_REBALANCE_PERIOD_SECS = 20 * 24 * 60 * 60  # 20 days (changed from 14 days)

class SnapshotError(Exception):
    """Base exception for snapshot-related errors."""
    pass

class SnapshotTimingError(SnapshotError):
    """Raised when snapshot is attempted outside allowed time window."""
    pass

class SnapshotParseError(SnapshotError):
    """Raised when btcli output cannot be parsed."""
    pass

@dataclass(frozen=True)
class EmissionSnapshot:
    # ts in ISO8601Z
    ts: str
    # TAO per day (or per period normalized to day) keyed by netuid
    emissions_by_netuid: Dict[int, float]
    # Optional metadata flags (immutable)
    low_trust: bool = False
    timing_policy: str = "strict"

"""Parsing Utilities"""

def _parse_json_emission(json_text: str, emission_col_name: str = "emission") -> Dict[int, float]:
    """Parse btcli JSON output for emissions data.
    
    Args:
        json_text: JSON output from btcli --output json
        emission_col_name: Field name to extract emissions from
        
    Returns:
        Dict mapping netuid -> daily emission in TAO
        
    Raises:
        SnapshotParseError: If JSON is malformed or missing required fields
    """
    import json
    import logging
    
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise SnapshotParseError(f"Invalid JSON from btcli: {e}") from e
    
    if not isinstance(data, (list, dict)):
        raise SnapshotParseError(f"Expected JSON array or object, got {type(data)}")
    
    # Handle different JSON formats btcli might return
    subnets = []
    if isinstance(data, list):
        subnets = data
    elif isinstance(data, dict):
        # Look for common container keys
        for key in ['subnets', 'data', 'results', 'items']:
            if key in data and isinstance(data[key], list):
                subnets = data[key]
                break
        else:
            # Single subnet object
            subnets = [data]
    
    out: Dict[int, float] = {}
    
    for subnet in subnets:
        if not isinstance(subnet, dict):
            continue
            
        try:
            # Extract netuid
            netuid = None
            for uid_key in ['netuid', 'uid', 'id', 'subnet_id']:
                if uid_key in subnet:
                    netuid = int(subnet[uid_key])
                    break
                    
            if netuid is None:
                # FIXED: Fail hard on malformed subnet objects
                raise SnapshotParseError(f"No netuid found in subnet object: {subnet}")
            
            # Extract emission - FAIL if missing
            emission_val = None
            for em_key in [emission_col_name, 'emission', 'daily_emission', 'emission_tao']:
                if em_key in subnet:
                    emission_str = str(subnet[em_key])
                    emission_val = _parse_strict_number(emission_str)
                    break
                    
            if emission_val is None:
                # FIXED: Fail hard on missing emission fields
                raise SnapshotParseError(
                    f"No emission field found for netuid {netuid} in JSON. "
                    f"Required fields: {[emission_col_name, 'emission', 'daily_emission', 'emission_tao']}"
                )
            
            out[netuid] = emission_val
            
        except (ValueError, KeyError) as e:
            raise SnapshotParseError(f"Failed to parse subnet data {subnet}: {e}") from e
    
    if not out:
        raise SnapshotParseError("No valid subnet data found in JSON output")
    
    # FIXED: Validate completeness against authoritative registry
    try:
        expected_netuids = _get_master_netuid_set_from_registry()
        missing_netuids = expected_netuids - set(out.keys())
        tolerance_env = os.environ.get("AM_JSON_MISSING_TOLERANCE", "0.0")
        try:
            tolerance = float(tolerance_env)
        except ValueError:
            tolerance = 0.0
        # Clamp to [0.0, 1.0]
        if tolerance < 0.0:
            tolerance = 0.0
        if tolerance > 1.0:
            tolerance = 1.0
        max_missing = int(len(expected_netuids) * tolerance)
        if missing_netuids and len(missing_netuids) > max_missing:
            raise SnapshotParseError(
                f"JSON snapshot missing {len(missing_netuids)} expected netuids (tolerance {max_missing}). "
                f"Examples: {sorted(missing_netuids)[:10]}"
            )
    except SnapshotError:
        # Registry unavailable - in strict mode, raise; otherwise continue
        settings = get_settings()
        if settings.strict_registry:
            raise
        pass
        
    logging.info(f"Parsed {len(out)} subnets from JSON format")
    return out

def _parse_table_emission(text: str, emission_col_name: str = "emission") -> Dict[int, float]:
    """Parse btcli subnet list output by header names, not magic indices.
    
    Args:
        text: btcli subnets list output
        emission_col_name: Header name to look for (case-insensitive)
    
    Returns:
        Dict mapping netuid -> daily emission in TAO
        
    Raises:
        ValueError: If header not found or table format unexpected
    """
    import re
    import logging
    
    lines = text.splitlines()
    if not lines:
        raise ValueError("Empty btcli output")
    
    # Find header line (contains column names)
    header_line = None
    header_idx = -1
    for i, line in enumerate(lines):
        # Look for line with table separators and common headers
        if any(sep in line for sep in ["│", "|"]) and any(word in line.lower() for word in ["netuid", "emission", "uid"]):
            header_line = line
            header_idx = i
            break
    
    if header_line is None:
        raise ValueError("Could not find header line in btcli output")
    
    # Parse headers - support both │ and | separators
    separator = "│" if "│" in header_line else "|"
    headers = [h.strip().lower() for h in header_line.split(separator)]
    
    # Find required columns
    try:
        netuid_col = next(i for i, h in enumerate(headers) if "uid" in h and "net" in h)
    except StopIteration:
        try:
            netuid_col = next(i for i, h in enumerate(headers) if h == "uid" or h == "netuid")
        except StopIteration:
            raise ValueError(f"Could not find netuid column in headers: {headers}")
    
    try:
        emission_col = next(i for i, h in enumerate(headers) if emission_col_name.lower() in h)
    except StopIteration:
        raise ValueError(f"Could not find column '{emission_col_name}' in headers: {headers}")
    
    logging.info(f"Found netuid column {netuid_col}, emission column {emission_col}")
    
    # Parse data rows
    out: Dict[int, float] = {}
    for line in lines[header_idx + 1:]:
        if separator not in line:
            continue
        parts = [p.strip() for p in line.split(separator)]
        if len(parts) <= max(netuid_col, emission_col):
            continue
            
        # Parse netuid
        try:
            netuid = int(parts[netuid_col])
        except (ValueError, IndexError):
            continue
            
        # Parse emission with STRICT validation - FAIL on any ambiguous data
        try:
            emission_str = parts[emission_col]
            emission_val = _parse_strict_number(emission_str)
            out[netuid] = emission_val
        except (ValueError, IndexError) as e:
            # FIXED: Fail the entire snapshot on any parse ambiguity
            raise SnapshotParseError(
                f"Failed to parse emission for netuid {netuid}: '{emission_str}' -> {e}"
            ) from e
            
    if not out:
        raise ValueError("No valid data rows found in btcli output")
        
    return out


def _parse_strict_number(text: str) -> float:
    """Parse number with strict validation - no coercion of invalid data to 0.0.
    
    Args:
        text: Input text that must be clearly numeric
        
    Returns:
        float: Parsed number
        
    Raises:
        ValueError: If text is not clearly numeric (including "N/A", "—", etc.)
    """
    import re
    
    if not text or text.strip() == "":
        # FIXED: Empty strings must fail hard, not coerce to 0.0
        raise ValueError("Empty emission value not allowed - must be explicit numeric zero")
        
    original_text = text.strip()
    
    # Explicit zero patterns are OK
    if original_text.lower() in ('0', '0.0', '0.00', '-0', '-0.0', '-0.00'):
        return 0.0
    
    # Check for non-numeric indicators that should fail hard
    non_numeric_patterns = [
        'n/a', 'na', 'nil', 'null', 'none', 'undefined',
        '—', '–', '-', '---', 'xxx', 'tbd', 'pending',
        'error', 'fail', 'invalid', '?', '??', '???'
    ]
    
    if original_text.lower() in non_numeric_patterns:
        raise ValueError(f"Non-numeric emission value '{original_text}' not allowed")
    
    # Allow only 'e'/'E' as alphabetic (scientific notation with optional sign). Any other letters fail.
    letters = [c for c in original_text if c.isalpha()]
    if letters and not all(c in ('e', 'E') for c in letters):
        raise ValueError(f"Text in emission value '{original_text}' not allowed")
    
    # Remove common formatting but preserve structure  
    cleaned = re.sub(r'[^\d\-+.,eE]', '', original_text)
    
    if not cleaned:
        raise ValueError(f"No numeric content in '{original_text}'")
    
    # Handle thousands separators
    if cleaned.count(',') > 1 or (cleaned.count(',') == 1 and cleaned.index(',') < len(cleaned) - 4):
        # Thousands separator: 1,234.56
        cleaned = cleaned.replace(',', '')
    elif ',' in cleaned and '.' not in cleaned:
        # European decimal: 1234,56 -> 1234.56
        cleaned = cleaned.replace(',', '.')
        
    try:
        result = float(cleaned)
        # Sanity check the result
        if abs(result) > 1e15:  # Unreasonably large emission
            raise ValueError(f"Emission value {result} too large in '{original_text}'")
        if result < 0.0:
            raise ValueError(f"Negative emission value {result} not allowed")
        return result
    except ValueError as e:
        # NO fallback extraction - fail hard on ambiguous data
        raise ValueError(f"Cannot parse emission '{original_text}' as number: {e}") from e

"""Snapshot Functions"""

def take_snapshot(btcli_path: str, network: str = "finney", emission_col_name: str = "emission", timeout_sec: int = 30, 
                 strict_timing: bool = True) -> EmissionSnapshot:
    """Take a snapshot using single deterministic timing policy (epoch cutover).
    
    Args:
        btcli_path: Path to btcli executable
        network: Network name (finney, test, local)
        emission_col_name: Column name to parse for emissions
        timeout_sec: Subprocess timeout
        strict_timing: If True, enforce epoch cutover ± grace window. If False, accept late with low-trust flag.
        
    Returns:
        EmissionSnapshot with timestamp and emissions data
        
    Raises:
        SnapshotTimingError: If outside allowed window in strict mode
        SnapshotError: If btcli command fails or parsing fails
    """
    import logging
    import os
    import time as time_
    
    settings = get_settings()

    # Metrics tracking  
    start_time = time_.time()
    _metrics.increment('snapshot_attempts')
    
    # Single deterministic timing policy using protocol constants
    now = datetime.datetime.now(datetime.timezone.utc)
    now_unix = int(now.timestamp())
    
    # Import protocol constants
    try:
        from ..sim.epoch import EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS, current_rebalance_id
        rebalance_id = current_rebalance_id(now_unix)
    except ImportError:
        # Use fallback constants
        EPOCH_ANCHOR_UNIX = _FALLBACK_EPOCH_ANCHOR_UNIX
        REBALANCE_PERIOD_SECS = _FALLBACK_REBALANCE_PERIOD_SECS
        rebalance_id = max(0, (now_unix - EPOCH_ANCHOR_UNIX) // REBALANCE_PERIOD_SECS)
    
    # Compute today's cutover inside the rebalance period (once per UTC day)
    epoch_start_unix = EPOCH_ANCHOR_UNIX + (rebalance_id * REBALANCE_PERIOD_SECS)
    seconds_since_epoch_start = now_unix - epoch_start_unix
    day_index = max(0, seconds_since_epoch_start // 86400)
    current_day_cutover_unix = epoch_start_unix + day_index * 86400
    epoch_day_cutover = datetime.datetime.fromtimestamp(current_day_cutover_unix, tz=datetime.timezone.utc)

    # Enforce grace window around the current day's cutover
    grace_period_sec = settings.snapshot_grace_sec
    window_start = epoch_day_cutover
    window_end = epoch_day_cutover + datetime.timedelta(seconds=grace_period_sec)
    
    is_late = not (window_start <= now <= window_end)
    low_trust = False
    
    if is_late:
        if strict_timing:
            # Strict mode: fail immediately, no retries
            _metrics.increment('timing_failures')
            _metrics.set_value('last_error', "timing_window_exceeded")
            emit_snapshot_metric("timing_failure", {
                "attempt_time": now.isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "policy": "strict"
            })
            raise SnapshotTimingError(
                f"Snapshot attempted at {now} outside strict window {window_start} to {window_end}. "
                f"Strict timing policy enforced."
            )
        else:
            # Permissive mode: accept but mark as low-trust
            low_trust = True
            logging.warning(f"Late snapshot at {now}, marking as low-trust")
            emit_snapshot_metric("late_snapshot_accepted", {
                "attempt_time": now.isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "policy": "permissive"
            })
    else:
        logging.info(f"Snapshot within window: {now} in [{window_start}, {window_end}]")
    
    # Execute btcli command - explicit mode selection
    proc_stdout = None
    json_mode = False
    
    # Try JSON mode first
    try:
        proc = subprocess.run(
            [btcli_path, "subnets", "list", "--network", network, "--output", "json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        proc_stdout = proc.stdout
        json_mode = True
        emit_snapshot_metric("btcli_mode", {"mode": "json", "success": True})
        logging.info("Using btcli JSON mode")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        # JSON mode failed, optionally try table mode if explicitly allowed
        emit_snapshot_metric("btcli_mode", {"mode": "json", "success": False})
        logging.warning(f"JSON mode failed: {e}")

        if not settings.allow_table_mode:
            # Fail closed in production
            raise SnapshotError("btcli JSON mode failed and table mode is disabled (ALLOW_TABLE_MODE=0)") from e

        logging.warning("Falling back to btcli table mode due to ALLOW_TABLE_MODE=1")
        try:
            proc = subprocess.run(
                [btcli_path, "subnets", "list", "--network", network],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            proc_stdout = proc.stdout
            json_mode = False
            emit_snapshot_metric("btcli_mode", {"mode": "table", "success": True})
            logging.info("Using btcli table mode")
        except subprocess.TimeoutExpired as e2:
            raise SnapshotError(f"btcli command timed out after {timeout_sec}s") from e2
        except subprocess.CalledProcessError as e2:
            raise SnapshotError(f"btcli command failed: {e2.stderr}") from e2
    
    # Parse output based on mode used
    try:
        if json_mode:
            em = _parse_json_emission(proc_stdout, emission_col_name=emission_col_name)
        else:
            em = _parse_table_emission(proc_stdout, emission_col_name=emission_col_name)
    except (ValueError, SnapshotParseError) as e:
        _metrics.increment('parse_failures')
        _metrics.set_value('last_error', "parse_failure")
        emit_snapshot_metric("parse_failure", {"error": str(e), "mode": "json" if json_mode else "table"})
        raise SnapshotError(f"Failed to parse btcli output: {e}") from e
        
    # Success metrics
    _metrics.increment('snapshot_successes')
    _metrics.set_value('netuids_seen', len(em))
    _metrics.set_value('total_emission', sum(em.values()))
    _metrics.set_value('runtime_seconds', time_.time() - start_time)
    
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    logging.info(f"Successfully captured emissions for {len(em)} subnets at {ts}")
    
    emit_snapshot_metric("snapshot_success", {
        "netuids": len(em),
        "total_emission": sum(em.values()),
        "runtime_sec": time_.time() - start_time,
        "mode": "json" if json_mode else "table",
        "low_trust": low_trust,
        "timing_policy": "strict" if strict_timing else "permissive"
    })
    
    # Create snapshot with immutable metadata
    snapshot = EmissionSnapshot(
        ts=ts, 
        emissions_by_netuid=em,
        low_trust=low_trust,
        timing_policy="strict" if strict_timing else "permissive"
    )
    
    return snapshot


def take_snapshot_map() -> Dict[int, float]:
    """DEPRECATED: Use take_snapshot() directly to preserve metadata.
    
    This helper discards low_trust and timing_policy metadata that validators need.
    
    Returns:
        Dict mapping netuid -> daily emission in TAO
        
    Raises:
        SnapshotError: On any snapshot failure (no silent {} returns)
    """
    import logging
    
    settings = get_settings()

    logging.warning(
        "take_snapshot_map() discards metadata. Use take_snapshot() directly "
        "to preserve low_trust and timing_policy for validator down-weighting."
    )
    
    btcli = settings.btcli_path
    if not btcli:
        raise SnapshotError("AM_BTCLI environment variable must be set")
        
    net = settings.network
    timeout = settings.btcli_timeout_sec
    
    try:
        snap = take_snapshot(btcli, network=net, timeout_sec=timeout)
        # FIXED: Emit warning when metadata is lost
        if snap.low_trust:
            logging.warning("Low-trust snapshot metadata lost via take_snapshot_map()")
        return snap.emissions_by_netuid
    except SnapshotTimingError:
        # Re-raise timing errors (they're policy violations)
        raise
    except SnapshotError:
        # Re-raise known snapshot errors
        raise
    except Exception as e:
        # FIXED: No more silent {} returns
        logging.error(f"Unexpected error in take_snapshot_map: {e}")
        raise SnapshotError(f"Unexpected snapshot failure: {e}") from e


def append_snapshot_tsv(out_dir: Path, snap: EmissionSnapshot) -> Path:
    """Append snapshot data with O(1) performance - includes trust metadata."""
    import fcntl
    import os
    
    settings = get_settings()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "emissions_daily.tsv"
    header = ["timestamp", "netuid", "emission_tao_per_day", "low_trust", "timing_policy"]
    
    # Check if we need to rotate first (keep append O(1))
    if path.exists():
        file_size = path.stat().st_size
        max_size = settings.max_tsv_size_mb * 1024 * 1024
        if file_size > max_size:
            rotate_emissions_file(out_dir)
    
    # Use file-based locking on the actual data file for coordination
    try:
        # Open for append with exclusive lock
        with open(path, "a", encoding="utf-8", newline="") as f:
            # Acquire exclusive lock on the data file itself
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            # Idempotency guard with trusted-upgrade allowance:
            # Skip duplicates only if an equal-or-more-trusted row already exists.
            idempotent = settings.idempotent_append
            existing_for_day: dict[int, bool] = {}
            if idempotent and path.exists():
                try:
                    target_day = _get_epoch_day_for_timestamp(snap.ts)
                    with open(path, "r", encoding="utf-8") as rf:
                        rdr = csv.DictReader(rf, delimiter="\t")
                        for r in rdr:
                            if r.get("timestamp") and _get_epoch_day_for_timestamp(r["timestamp"]) == target_day:
                                try:
                                    uid = int(r["netuid"])
                                    low_str = str(r.get("low_trust", "false")).strip().lower()
                                    is_low = low_str in ("1", "true", "yes", "y", "t")
                                    existing_for_day[uid] = existing_for_day.get(uid, True) and is_low
                                except Exception:
                                    continue
                except Exception:
                    existing_for_day = {}

            # Write header only if file is empty
            if f.tell() == 0:
                w = csv.writer(f, delimiter="\t")
                w.writerow(header)

            # Append new data rows with metadata - this is O(k) where k = new rows, not O(total file size)
            w = csv.writer(f, delimiter="\t")
            for k, v in sorted(snap.emissions_by_netuid.items()):
                if idempotent:
                    existing_is_low = existing_for_day.get(k)
                    if existing_is_low is None:
                        pass  # No existing row for this day
                    else:
                        # If existing row is trusted (False) and incoming is trusted or low, skip
                        if existing_is_low is False:
                            continue
                        # If existing is low (True) and incoming is low, skip
                        if existing_is_low is True and snap.low_trust is True:
                            continue
                        # If existing is low and incoming is trusted, allow overwrite by writing new row
                w.writerow([snap.ts, k, v, snap.low_trust, snap.timing_policy])

            # Ensure data is written
            f.flush()
            os.fsync(f.fileno())
                
    except (OSError, IOError) as e:
        raise SnapshotError(f"Failed to append to emissions TSV: {e}") from e
    
    emit_snapshot_metric("tsv_append", {
        "rows_added": len(snap.emissions_by_netuid),
        "file_size_mb": path.stat().st_size / (1024 * 1024)
    })
    
    return path

"""Observability and Metrics"""

class SnapshotMetrics:
    """Thread-safe structured metrics for snapshot operations."""
    
    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self.reset()
    
    def reset(self):
        with self._lock:
            self.snapshot_attempts = 0
            self.snapshot_successes = 0
            self.parse_failures = 0
            self.timing_failures = 0
            self.retries_used = 0
            self.netuids_seen = 0
            self.eligible_subnets = 0
            self.total_emission = 0.0
            self.runtime_seconds = 0.0
            self.last_error = None
    
    def increment(self, field: str, value: int = 1):
        """Thread-safe increment of metric counter."""
        with self._lock:
            current = getattr(self, field, 0)
            setattr(self, field, current + value)
    
    def set_value(self, field: str, value):
        """Thread-safe set of metric value."""
        with self._lock:
            setattr(self, field, value)
        
    def to_dict(self) -> dict:
        with self._lock:
            return {
                "snapshot_success_rate": self.snapshot_successes / max(1, self.snapshot_attempts),
                "parse_failure_rate": self.parse_failures / max(1, self.snapshot_attempts),
                "timing_failure_rate": self.timing_failures / max(1, self.snapshot_attempts),
                "avg_retries": self.retries_used / max(1, self.snapshot_attempts),
                "netuids_seen": self.netuids_seen,
                "eligible_subnets": self.eligible_subnets,
                "total_emission_tao": self.total_emission,
                "runtime_seconds": self.runtime_seconds,
                "last_error": self.last_error,
            }

# Global thread-safe metrics instance
_metrics = SnapshotMetrics()

def get_snapshot_metrics() -> dict:
    """Get current snapshot metrics for monitoring."""
    return _metrics.to_dict()

def emit_snapshot_metric(metric_name: str, value: Any = None):
    """Emit a structured metric event with full audit context."""
    import logging
    import json
    import os
    
    settings = get_settings()
    
    # Get current rebalance context for auditing
    rebalance_id = int(os.environ.get('AM_REBALANCE_ID', '0'))
    utc_anchor = _get_canonical_utc_anchor(rebalance_id)
    
    metric_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metric": metric_name,
        "value": value,
        "component": "snapshot",
        "audit_context": {
            "rebalance_id": rebalance_id,
            "utc_anchor_date": utc_anchor.isoformat(),
            "window_14d_start": (utc_anchor - datetime.timedelta(days=13)).isoformat(),
            "window_90d_start": (utc_anchor - datetime.timedelta(days=89)).isoformat(),
            "snapshot_window_utc": _get_epoch_cutover_timestamp(rebalance_id)
        }
    }
    
    # Structured logging for metric ingestion with audit trail
    logging.info(f"METRIC: {json.dumps(metric_data, separators=(',', ':'))}")

"""File Retention and Rotation"""

def rotate_emissions_file(out_dir: Path, max_days: int = 120) -> None:
    """Rotate emissions file by rewriting in place under lock.

    This avoids the rename race: we lock the current inode, read, filter,
    seek(0) → truncate(0) → write → fsync, then unlock. Writers will block
    on the same lock and cannot race onto a new inode.
    """
    import csv as _csv
    import fcntl
    import shutil
    from datetime import timedelta

    settings = get_settings()

    daily_tsv = out_dir / "emissions_daily.tsv"
    if not daily_tsv.exists():
        return

    # Calculate cutoff date using canonical anchor
    utc_anchor = _get_canonical_utc_anchor()
    cutoff_date = (utc_anchor - timedelta(days=max_days)).isoformat()

    # Preserve original file with timestamp
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    preserved_original = out_dir / f"emissions_daily_pre_rotation_{timestamp}.tsv"

    try:
        with open(daily_tsv, "r+", encoding="utf-8", newline="") as f:
            # Lock the data file itself
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            # Preserve original file while holding the lock
            shutil.copy2(daily_tsv, preserved_original)

            # Read all rows
            f.seek(0)
            reader = _csv.DictReader(f, delimiter='\t')
            header = reader.fieldnames or ["timestamp", "netuid", "emission_tao_per_day", "low_trust", "timing_policy"]
            original_rows = 0
            recent_rows = []
            for row in reader:
                original_rows += 1
                ts = row.get('timestamp', '')
                day = _get_epoch_day_for_timestamp(ts)
                if day >= cutoff_date:
                    recent_rows.append(row)

            # Rewrite in place
            f.seek(0)
            f.truncate(0)
            writer = _csv.DictWriter(f, fieldnames=header, delimiter='\t')
            writer.writeheader()
            if recent_rows:
                writer.writerows(recent_rows)
            f.flush()
            os.fsync(f.fileno())

        emit_snapshot_metric("file_rotation", {
            "max_days": max_days,
            "original_rows": original_rows,
            "rows_retained": len(recent_rows),
            "rows_dropped": original_rows - len(recent_rows),
            "cutoff_date": cutoff_date,
            "preserved_file": str(preserved_original)
        })

        logging.info(
            f"Rotated emissions file: {original_rows} -> {len(recent_rows)} rows, preserved original as {preserved_original}"
        )

    except (OSError, IOError) as e:
        raise SnapshotError(f"Failed to rotate emissions file: {e}") from e

"""Day Boundary and Timing Utilities"""

def _get_epoch_cutover_timestamp(rebalance_id: int) -> str:
    """Get the actual epoch cutover timestamp in ISO format.
    
    Args:
        rebalance_id: Rebalance epoch ID
        
    Returns:
        ISO timestamp of the epoch cutover (e.g., "2024-08-14T00:00:00Z")
    """
    # Import protocol constants
    try:
        from ..sim.epoch import EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS
    except ImportError:
        EPOCH_ANCHOR_UNIX = _FALLBACK_EPOCH_ANCHOR_UNIX
        REBALANCE_PERIOD_SECS = _FALLBACK_REBALANCE_PERIOD_SECS
    
    epoch_start_unix = EPOCH_ANCHOR_UNIX + (rebalance_id * REBALANCE_PERIOD_SECS)
    epoch_dt = datetime.datetime.fromtimestamp(epoch_start_unix, tz=datetime.timezone.utc)
    return epoch_dt.isoformat().replace('+00:00', 'Z')

def _get_epoch_day_for_timestamp(ts_iso: str) -> str:
    """Convert ISO timestamp to epoch-aligned day bucket.
    
    Uses protocol constants to ensure consistent day boundaries across all components.
    Day buckets start at the epoch cutover time, not UTC midnight.
    
    Args:
        ts_iso: ISO8601 timestamp (e.g., "2024-01-15T16:30:00Z")
        
    Returns:
        str: ISO date string representing the epoch day bucket (e.g., "2024-01-15")
    """
    import datetime
    
    # Import protocol constants
    try:
        from ..sim.epoch import EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS
    except ImportError:
        EPOCH_ANCHOR_UNIX = _FALLBACK_EPOCH_ANCHOR_UNIX
        REBALANCE_PERIOD_SECS = _FALLBACK_REBALANCE_PERIOD_SECS
    
    # Parse timestamp
    dt = datetime.datetime.fromisoformat(ts_iso.replace('Z', '+00:00'))
    ts_unix = int(dt.timestamp())
    
    # FIXED: Handle pre-anchor timestamps properly
    if ts_unix < EPOCH_ANCHOR_UNIX:
        # Pre-anchor: map to day 0 (epoch anchor date)
        anchor_dt = datetime.datetime.fromtimestamp(EPOCH_ANCHOR_UNIX, tz=datetime.timezone.utc)
        return anchor_dt.date().isoformat()
    
    # Calculate which rebalance period this timestamp falls in
    periods_since_anchor = (ts_unix - EPOCH_ANCHOR_UNIX) // REBALANCE_PERIOD_SECS
    period_start_unix = EPOCH_ANCHOR_UNIX + (periods_since_anchor * REBALANCE_PERIOD_SECS)
    
    # Calculate day within the period (each rebalance period = 14 days)
    day_offset_sec = ts_unix - period_start_unix
    day_offset = day_offset_sec // (24 * 60 * 60)
    
    # Clamp day_offset to valid range [0, 13] within the rebalance period
    day_offset = max(0, min(day_offset, 13))
    
    # Get the actual calendar date for this epoch day
    day_start_unix = period_start_unix + (day_offset * 24 * 60 * 60)
    day_dt = datetime.datetime.fromtimestamp(day_start_unix, tz=datetime.timezone.utc)
    
    return day_dt.date().isoformat()


"""Utility Functions"""

def _get_canonical_utc_anchor(rebalance_id: int = None) -> "datetime.date":
    """Get canonical UTC anchor from protocol constants, ensuring consistency.
    
    Uses single source of truth: EPOCH_ANCHOR_UNIX + REBALANCE_PERIOD_SECS * rebalance_id
    This ensures identical windows across all nodes for the same rebalance_id.
    
    Args:
        rebalance_id: Current rebalance epoch ID for deterministic anchor
        
    Returns:
        UTC date that all nodes will use for the same rebalance_id
    """
    from datetime import datetime, timezone, timedelta
    import os
    
    settings = get_settings()
    
    # Import protocol constants
    try:
        from ..sim.epoch import EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS, current_rebalance_id
    except ImportError:
        # Use fallback constants if epoch module unavailable
        EPOCH_ANCHOR_UNIX = _FALLBACK_EPOCH_ANCHOR_UNIX
        REBALANCE_PERIOD_SECS = _FALLBACK_REBALANCE_PERIOD_SECS
        import time
        def current_rebalance_id(now_unix=None):
            if now_unix is None:
                now_unix = int(time.time())
            return max(0, (now_unix - EPOCH_ANCHOR_UNIX) // REBALANCE_PERIOD_SECS)
    
    # Get rebalance_id from parameter or current
    if rebalance_id is None:
        # Try environment first, then calculate current
        env_id = os.environ.get('AM_REBALANCE_ID')
        if env_id:
            rebalance_id = int(env_id)
        else:
            rebalance_id = current_rebalance_id()
    
    # Calculate canonical UTC date from protocol anchor
    epoch_unix = EPOCH_ANCHOR_UNIX + (rebalance_id * REBALANCE_PERIOD_SECS)
    canonical_dt = datetime.fromtimestamp(epoch_unix, tz=timezone.utc)
    
    return canonical_dt.date()


def _get_utc_anchor_date(daily_tsv: Path) -> "datetime.date":
    """DEPRECATED: Use _get_canonical_utc_anchor() for consistency.
    
    This function is kept for backward compatibility but should not be used
    for production window calculations.
    """
    import logging
    logging.warning("_get_utc_anchor_date() is deprecated. Use _get_canonical_utc_anchor()")
    
    # Fallback to canonical anchor
    return _get_canonical_utc_anchor()


def _get_min_emission_threshold() -> float:
    """Get minimum emission threshold from environment or default."""
    return get_settings().min_emission_threshold


def _get_master_netuid_set_from_registry() -> set[int]:
    """Get authoritative netuid set from on-chain registry or validator set.
    
    This ensures we evaluate ALL known subnets, not just those in recent TSV.
    """
    import json
    import logging

    settings = get_settings()
    
    # Try to get from validator service (authoritative source)
    try:
        from ..validator.service import get_known_netuids
        known_netuids = get_known_netuids()
        if known_netuids:
            logging.info(f"Got {len(known_netuids)} netuids from validator registry")
            return set(known_netuids)
    except (ImportError, AttributeError):
        pass
    
    # Try registry file if available
    registry_file = settings.netuid_registry_file
    if registry_file:
        try:
            with open(registry_file, 'r') as f:
                registry = json.load(f)
                netuids = set(int(uid) for uid in registry.get('active_netuids', []))
                if netuids:
                    logging.info(f"Got {len(netuids)} netuids from registry file")
                    return netuids
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Failed to load netuid registry: {e}")
    
    # Fallback to environment variable list
    env_netuids = settings.known_netuids
    if env_netuids:
        try:
            netuids = set(int(uid.strip()) for uid in env_netuids.split(',') if uid.strip())
            if netuids:
                logging.info(f"Got {len(netuids)} netuids from environment")
                return netuids
        except ValueError as e:
            logging.warning(f"Failed to parse AM_KNOWN_NETUIDS: {e}")
    
    # FIXED: Fail closed - no fallback ranges in production
    if settings.strict_registry:
        raise SnapshotError(
            "FATAL: No authoritative netuid registry available. "
            "Production requires registry via validator service, AM_NETUID_REGISTRY file, "
            "or AM_KNOWN_NETUIDS environment variable. "
            "Set AM_STRICT_REGISTRY=0 to use fallback range (NOT recommended)."
        )
    
    # Emergency fallback only if explicitly allowed
    logging.error("EMERGENCY: Using fallback netuid range 1-50. Set AM_STRICT_REGISTRY=1 for production safety.")
    return set(range(1, 51))


def _get_master_netuid_set(daily_tsv: Path = None, window_days: int = 120) -> set[int]:
    """Get master set combining authoritative registry + recent TSV history.
    
    This ensures we capture both registered subnets and any new ones in TSV.
    """
    import csv as _csv
    from datetime import timedelta
    
    # Start with authoritative registry
    all_netuids = _get_master_netuid_set_from_registry()
    
    # Augment with TSV history for any new registrations
    if daily_tsv and daily_tsv.exists():
        try:
            utc_anchor = _get_canonical_utc_anchor()
            cutoff_date = (utc_anchor - timedelta(days=window_days)).isoformat()
            
            with open(daily_tsv, 'r', encoding='utf-8') as f:
                reader = _csv.DictReader(f, delimiter='\t')
                for row in reader:
                    try:
                        ts = row['timestamp']
                        day = _get_epoch_day_for_timestamp(ts)
                        if day >= cutoff_date:  # Only recent data
                            netuid = int(row['netuid'])
                            all_netuids.add(netuid)
                    except (ValueError, KeyError):
                        continue
        except (OSError, IOError):
            pass
    
    emit_snapshot_metric("master_netuid_set", {
        "total_netuids": len(all_netuids),
        "source": "registry_plus_tsv"
    })
    
    return all_netuids


"""Computation Functions"""

def compute_rolling_14d(out_dir: Path) -> Path:
    """FIXED: Compute 14-day average emissions using UTC calendar days and streaming.
    
    Uses last 14 calendar days from UTC anchor, treats missing days as zero.
    Memory usage is bounded regardless of file size.
    """
    from datetime import date, timedelta, datetime, timezone
    import csv as _csv
    
    settings = get_settings()

    daily = out_dir / "emissions_daily.tsv"
    out = out_dir / "emissions_14d.tsv"
    if not daily.exists():
        return out
    
    # FIXED: Use canonical UTC anchor tied to rebalance epoch
    utc_anchor = _get_canonical_utc_anchor()
    calendar_days = [(utc_anchor - timedelta(days=i)).isoformat() 
                     for i in range(14)]
    calendar_day_set = set(calendar_days)
    
    # FIXED: Get master netuid set to include all-zero subnets
    all_netuids = _get_master_netuid_set(daily)
    
    # Stream file and collect data for only the last 14 calendar days
    # Store (value, is_low_trust) and prefer trusted over low-trust when both exist
    by_day: Dict[str, Dict[int, tuple[float, bool]]] = defaultdict(dict)
    
    with open(daily, "r", encoding="utf-8") as f:
        reader = _csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                ts = row["timestamp"]
                day = _get_epoch_day_for_timestamp(ts)  # Use consistent day boundary
                
                # Only process if it's in our 14-day window
                if day not in calendar_day_set:
                    continue
                    
                netuid = int(row["netuid"])
                val = float(row["emission_tao_per_day"]) or 0.0
                # Legacy compatibility: default to trusted if column missing
                low_str = str(row.get("low_trust", "false")).strip().lower()
                is_low = low_str in ("1", "true", "yes", "y", "t")

                # Policy: exclude low-trust rows by default unless env override
                if not settings.include_low_trust_14d and is_low:
                    # Skip low-trust data entirely
                    continue

                # Prefer trusted over low-trust if both exist
                existing = by_day[day].get(netuid)
                if existing is None:
                    by_day[day][netuid] = (val, is_low)
                else:
                    prev_val, prev_low = existing
                    if prev_low and not is_low:
                        by_day[day][netuid] = (val, is_low)
                    else:
                        # Same trust level or new is low-trust when trusted exists: keep existing
                        by_day[day][netuid] = (val, is_low) if not prev_low and not is_low else existing
                
            except (ValueError, KeyError):
                continue
    
    # Policy: exclude low-trust rows from 14d averages unless explicitly allowed
    allow_low_trust = settings.include_low_trust_14d

    # Compute averages with missing days = 0
    sum_map: Dict[int, float] = defaultdict(float)
    
    for day in calendar_days:
        daily_data = by_day.get(day, {})
        for netuid in all_netuids:
            tup = daily_data.get(netuid)
            if tup is None:
                val = 0.0
            else:
                val, is_low = tup
                if not allow_low_trust and is_low:
                    val = 0.0
            sum_map[netuid] += val
    
    # Write results (include all netuids, even all-zero)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["netuid", "avg_14d_emission_tao_per_day", "days_counted"])
        for netuid in sorted(all_netuids):
            total = sum_map.get(netuid, 0.0)
            avg = total / 14.0
            writer.writerow([netuid, avg, 14])
    
    return out

# Unit test stub:
# def test_rolling_avg_with_gaps():
#     # Simulate TSV with gaps for netuid 1 (e.g., 10 days data, 4 missing -> avg = sum/14)
#     # Assert avg < sum/10

def compute_eligibility_3m(out_dir: Path) -> Path:
    """FIXED: Check subnet eligibility using exactly 90 consecutive UTC calendar days.
    
    Rule: A subnet is eligible if it has >min_threshold emission on ALL of the last 90 calendar days.
    Any single day with insufficient emission = ineligible.
    
    This fixes the major bug where missing days were ignored instead of counted as zeros.
    """
    from datetime import date, timedelta
    import csv as _csv
    
    settings = get_settings()

    daily = out_dir / "emissions_daily.tsv"
    out = out_dir / "eligibility_3m.tsv"
    if not daily.exists():
        return out
    
    # FIXED: Use canonical UTC anchor tied to rebalance epoch
    utc_anchor = _get_canonical_utc_anchor()
    min_threshold = settings.min_emission_threshold
    calendar_days = [(utc_anchor - timedelta(days=i)).isoformat() 
                     for i in range(90)]
    calendar_day_set = set(calendar_days)
    
    # FIXED: Get master netuid set to ensure all known subnets are evaluated
    all_netuids = _get_master_netuid_set(daily)
    
    # Load emissions data for only the relevant 90 days
    # Keep (value, is_low_trust) and prefer trusted over low-trust when both exist
    by_day: Dict[str, Dict[int, tuple[float, bool]]] = defaultdict(dict)
    
    with open(daily, "r", encoding="utf-8") as f:
        reader = _csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                ts = row["timestamp"]
                day = _get_epoch_day_for_timestamp(ts)  # Use consistent day boundary
                
                # Only process if it's in our 90-day window
                if day not in calendar_day_set:
                    continue
                    
                netuid = int(row["netuid"])
                val = float(row["emission_tao_per_day"]) or 0.0
                low_str = str(row.get("low_trust", "false")).strip().lower()
                is_low = low_str in ("1", "true", "yes", "y", "t")

                existing = by_day[day].get(netuid)
                if existing is None:
                    by_day[day][netuid] = (val, is_low)
                else:
                    prev_val, prev_low = existing
                    if prev_low and not is_low:
                        by_day[day][netuid] = (val, is_low)
                    else:
                        by_day[day][netuid] = (val, is_low) if not prev_low and not is_low else existing
                
            except (ValueError, KeyError):
                continue
    
    # Policy: treat low-trust as zero unless override
    include_low = settings.include_low_trust_elig

    # Check eligibility: ALL 90 days must have > threshold emission
    eligible: Dict[int, int] = {}
    
    for netuid in all_netuids:
        is_eligible = True
        
        # Check EVERY calendar day in the 90-day window against threshold
        for day in calendar_days:
            tup = by_day.get(day, {}).get(netuid)
            emission = 0.0 if tup is None else (tup[0] if (include_low or not tup[1]) else 0.0)
            if emission <= min_threshold:
                is_eligible = False
                break  # Any single day below threshold = ineligible
        
        eligible[netuid] = 1 if is_eligible else 0
    
    # Write results
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = _csv.writer(f, delimiter="\t")
        writer.writerow(["netuid", "eligible_3m"])
        for netuid in sorted(eligible.keys()):
            writer.writerow([netuid, eligible[netuid]])
    
    # Emit eligibility metrics
    eligible_count = sum(eligible.values())
    emit_snapshot_metric("eligibility_computed", {
        "total_netuids": len(eligible),
        "eligible_count": eligible_count,
        "eligibility_rate": eligible_count / max(1, len(eligible)),
        "min_threshold": min_threshold
    })
    
    return out

# Unit test stub:
# def test_eligibility_with_gap():
#     # Simulate 90 days with zero on day -30
#     # Assert not eligible despite total >90 nonzero


def compute_weights(top_20_emissions: Dict[int, float]) -> Dict[int, float]:
    """REMOVED: This function is a divergence footgun.
    
    Use the canonical validator normalization path directly.
    """
    raise RuntimeError(
        "compute_weights() has been removed to prevent normalization divergence. "
        "Use the canonical validator normalization path: "
        "from subnet.validator.service import normalize_weights_canonical"
    )

