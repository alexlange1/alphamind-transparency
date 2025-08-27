#!/usr/bin/env python3
from __future__ import annotations

import glob
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Iterable, Tuple, Optional, Sequence
import hashlib

from ..tao20.models import EmissionsReport, WeightSet
from ..tao20.validator import compute_index_weights_from_reports
from ..tao20.reports import PriceReport, NavReport
from ..tao20.consensus import WeightedValue, aggregate_map_median
from ..common.stake_oracle import load_stake_oracle
from ..common.bt_signing import verify_with_ss58
from ..common.crypto import verify_signature as verify_hmac
from ..sim.vault import VaultState, load_vault, save_vault, initialize_vault, compute_nav
from ..sim.epoch import current_epoch_id, current_rebalance_id
from ..common.settings import get_settings
from .publish import publish_weightset
from .state import is_paused
from .scoring import apply_deviation as scoring_apply_deviation
from .scoring import weight_multiplier as scoring_weight_multiplier
from .scoring import is_suspended as scoring_is_suspended
from .scoreboard import Scoreboard, get_multiplier_from_scores

from functools import lru_cache


def _load_and_verify_reports(in_dir: Path, report_type: str, from_json_func):
    def report_generator():
        reject_hmac = os.environ.get("AM_REJECT_HMAC", "0") == "1"
        
        for path in glob.glob(str(in_dir / f"{report_type}_*_*.json")):
            try:
                text = Path(path).read_text(encoding="utf-8")
                rep = from_json_func(text)
                
                if rep.signature:
                    ok = True
                    if rep.signer_ss58:
                        ok = verify_with_ss58(text.encode("utf-8"), rep.signature, rep.signer_ss58)
                    elif not reject_hmac:
                        try:
                            import logging as _log
                            _log.getLogger("validator").warning(
                                "accepting HMAC/non-hotkey %s report from %s (legacy)",
                                report_type,
                                rep.miner_id
                            )
                        except Exception:
                            pass
                    else:
                        ok = False
                    
                    if not ok:
                        continue

                if scoring_is_suspended(in_dir, rep.signer_ss58 or rep.miner_id):
                    continue
                
                yield rep
            except Exception:
                continue
            
    return list(report_generator())  # Materialize only if needed


def load_reports(in_dir: Path) -> List[EmissionsReport]:
    return _load_and_verify_reports(in_dir, "emissions", EmissionsReport.from_json)


def load_price_reports(in_dir: Path) -> List[PriceReport]:
    return _load_and_verify_reports(in_dir, "prices", PriceReport.from_json)


def load_nav_reports(in_dir: Path) -> List[NavReport]:
    return _load_and_verify_reports(in_dir, "nav", NavReport.from_json)


def extract_reserves_from_price_reports(price_reports: List[PriceReport]) -> Dict[int, Tuple[float, float]]:
    """Aggregate pool reserves for each netuid from PriceReport.prices entries when present.

    Returns mapping netuid -> (reserve_token_qty, reserve_tao_qty) using medians across reports.
    Missing or invalid entries are ignored.
    """
    from statistics import median
    pools: Dict[int, List[Tuple[float, float]]] = {}
    for pr in price_reports:
        items = getattr(pr, "prices", None) or []
        for it in items:
            try:
                uid = int(getattr(it, "uid"))
                rtok = getattr(it, "pool_reserve_token", None)
                rtao = getattr(it, "pool_reserve_tao", None)
                if rtok is None or rtao is None:
                    continue
                vt = float(rtok)
                va = float(rtao)
                if vt > 0 and va > 0:
                    pools.setdefault(uid, []).append((vt, va))
            except Exception:
                continue
    out: Dict[int, Tuple[float, float]] = {}
    for uid, arr in pools.items():
        try:
            vt_med = median([x for (x, _y) in arr])
            va_med = median([y for (_x, y) in arr])
            if vt_med > 0 and va_med > 0:
                out[uid] = (float(vt_med), float(va_med))
        except Exception:
            continue
    return out


def _parse_iso8601_z(ts: str) -> datetime:
    try:
        # Expect format like 2025-01-01T00:00:00Z
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            # Fallback: fromisoformat may handle offsets but not 'Z'
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return datetime.fromtimestamp(0, tz=timezone.utc)


def consensus_prices(price_reports: List[PriceReport]) -> Dict[int, float]:
    # Baseline consensus: stake-agnostic median across all reports
    buckets: Dict[int, List[WeightedValue]] = {}
    for rep in price_reports:
        for netuid, price in rep.prices_by_netuid.items():
            buckets.setdefault(netuid, []).append(WeightedValue(value=float(price), weight=1.0))
    return aggregate_map_median(buckets)


def validate_price_freshness(price_reports: List[PriceReport], max_age_minutes: int = 5) -> List[PriceReport]:
    """Filter price reports to only include fresh ones"""
    from datetime import datetime, timezone, timedelta
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    
    fresh_reports = []
    for report in price_reports:
        try:
            report_time = _parse_iso8601_z(report.ts)
            if report_time >= cutoff:
                fresh_reports.append(report)
        except Exception:
            # Skip malformed timestamps
            continue
    
    return fresh_reports


def have_price_quorum_for_uid(uid: int, price_reports: List[PriceReport], stake_by_miner: Dict[str, float], quorum_threshold: float) -> bool:
    # Compute coverage specific to uid in window using consensus_prices_with_twap mechanics
    prices, quorum_map, _stale = consensus_prices_with_twap(
        price_reports,
        stake_by_miner=stake_by_miner,
        window_minutes=30,
        outlier_k=5.0,
        quorum_threshold=quorum_threshold,
        price_band_pct=float(os.environ.get("AM_PRICE_BAND_PCT", 0.2)),
        stale_sec=int(os.environ.get("AM_PRICE_STALE_SEC", 120)),
        out_dir=None,
    )
    return float(quorum_map.get(int(uid), 0.0)) >= float(quorum_threshold) and int(uid) in prices


def have_global_price_quorum(price_reports: List[PriceReport], stake_by_miner: Dict[str, float], quorum_threshold: float) -> bool:
    _p, quorum_map, _s = consensus_prices_with_twap(
        price_reports,
        stake_by_miner=stake_by_miner,
        window_minutes=30,
        outlier_k=5.0,
        quorum_threshold=quorum_threshold,
        price_band_pct=float(os.environ.get("AM_PRICE_BAND_PCT", 0.2)),
        stale_sec=int(os.environ.get("AM_PRICE_STALE_SEC", 120)),
        out_dir=None,
    )
    if not quorum_map:
        return False
    return all(float(v) >= float(quorum_threshold) for v in quorum_map.values())


@lru_cache(maxsize=128)
def _median(vals: Tuple[float]) -> float:
    sorted_vals = sorted(vals)
    mid = len(sorted_vals) // 2
    return sorted_vals[mid] if len(sorted_vals) % 2 == 1 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def _mad(values: List[float], med: float) -> float:
    if not values:
        return 0.0
    deviations = [abs(v - med) for v in values]
    return _median(deviations)


def build_miner_stake_map(emission_reports: List[EmissionsReport]) -> Dict[str, float]:
    # Prefer external oracle when provided; fallback to latest stake in reports
    try:
        oracle, _age = load_stake_oracle()
        if oracle:
            return {str(k): float(v) for k, v in oracle.items()}
    except Exception:
        pass
    latest_ts: Dict[str, str] = {}
    out: Dict[str, float] = {}
    for r in emission_reports:
        mid = r.miner_id
        ts = r.snapshot_ts
        if mid not in latest_ts or ts > latest_ts[mid]:
            latest_ts[mid] = ts
            out[mid] = float(r.stake_tao)
    return out


def consensus_prices_with_twap(
    price_reports: List[PriceReport],
    stake_by_miner: Dict[str, float],
    window_minutes: int = 30,
    outlier_k: float = 5.0,
    quorum_threshold: float = 0.7,
    price_band_pct: float = 0.2,
    stale_sec: int = 120,
    out_dir: Optional[Path] = None,
    max_reports: int = 1000,
    max_uids_per_report: int = 1000
) -> Tuple[Dict[int, float], Dict[int, float], Dict[int, float]]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    # Collect samples
    samples: Dict[int, List[Tuple[str, float, float, bool, str, datetime]]] = {}
    pin_times: Dict[int, List[datetime]] = {}
    # tuple: (miner_id, price, stake, in_window)
    for rep in price_reports[:max_reports]:
        rep_dt = _parse_iso8601_z(rep.ts)
        # Prefer block_time if present for windowing
        pin_dt = _parse_iso8601_z(getattr(rep, "block_time", "")) if getattr(rep, "block_time", "") else rep_dt
        is_stale = (now - pin_dt) > timedelta(seconds=max(0, int(stale_sec)))
        in_win = (pin_dt >= window_start) and not is_stale
        miner_stake = float(stake_by_miner.get(rep.miner_id, 0.0))
        
        # Limit the number of uids to process per report
        uid_count = 0
        for netuid, price in rep.prices_by_netuid.items():
            if uid_count >= max_uids_per_report:
                break
            samples.setdefault(netuid, []).append((rep.miner_id, float(price), miner_stake, in_win, rep.ts, pin_dt))
            pin_times.setdefault(netuid, []).append(pin_dt)
            uid_count += 1
            
        if is_stale and out_dir is not None:
            try:
                logp = out_dir / "slashing_log.jsonl"
                with open(logp, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "type": "price_stale",
                        "miner_id": rep.miner_id,
                        "block_time": getattr(rep, "block_time", ""),
                        "stale_sec": (now - pin_dt).total_seconds(),
                    }, separators=(",", ":")) + "\n")
            except Exception:
                pass

    # All-time weighted median per net for fallback
    all_buckets: Dict[int, List[WeightedValue]] = {}
    for netuid, arr in samples.items():
        for (_mid, price, stake, _in_win, _ts, _pin) in arr:
            if stake > 0:
                all_buckets.setdefault(netuid, []).append(WeightedValue(value=price, weight=stake))
    all_time = aggregate_map_median(all_buckets)

    # Windowed with outlier filter and quorum check
    prices_out: Dict[int, float] = {}
    quorum_meta: Dict[int, float] = {}
    staleness_meta: Dict[int, float] = {}
    total_stake = sum(max(0.0, s) for s in stake_by_miner.values()) or 1.0
    offenders: List[Dict[str, object]] = []
    for netuid, arr in samples.items():
        win_vals = [price for (_mid, price, _stake, in_win, _ts, _pin) in arr if in_win]
        if not win_vals:
            prices_out[netuid] = all_time.get(netuid, 0.0)
            quorum_meta[netuid] = 0.0
            # staleness as seconds since freshest pin_dt across all samples
            pts = pin_times.get(netuid, [])
            freshest = max(pts) if pts else window_start
            staleness_meta[netuid] = float((now - freshest).total_seconds())
            continue
        med = _median(win_vals)
        mad = _mad(win_vals, med)
        # Filter values outside k * MAD
        filtered: List[Tuple[str, float, float]] = []  # (miner_id, price, stake)
        win_stake_sum = 0.0
        for (mid, price, stake, in_win, ts_str, pin_dt) in arr:
            if not in_win:
                continue
            if mad > 0 and abs(price - med) > outlier_k * mad:
                offenders.append({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "type": "deviation",
                    "metric": "price",
                    "uid": int(netuid),
                    "report_value": float(price),
                    "median": float(med),
                    "pct_diff": (abs(price - med) / med * 100.0) if med else 0.0,
                    "miner_hotkey": mid,
                })
                try:
                    pct_bps = int(abs(price - med) / med * 10000.0) if med else 0
                    scoring_apply_deviation(out_dir or Path("."), mid, pct_bps)
                    # Scoreboard: record price sample
                    try:
                        from .scoreboard import Scoreboard
                        scb = Scoreboard(out_dir or Path("."))
                        # Slot early calculation
                        interval = int(os.environ.get("AM_PRICE_INTERVAL_SEC", 60))
                        slot_start = int(pin_dt.timestamp() // max(1, interval)) * max(1, interval)
                        early = (int(pin_dt.timestamp()) - slot_start) <= (max(1, interval) // 2)
                        scb.record_price_sample(mid, ts_str, pct_bps, early)
                    except Exception:
                        pass
                except Exception:
                    pass
                continue
            # Enforce band relative to median (e.g., 20%)
            if med > 0 and abs(price - med) / med > max(0.0, price_band_pct):
                offenders.append({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "type": "deviation",
                    "metric": "price",
                    "uid": int(netuid),
                    "report_value": float(price),
                    "median": float(med),
                    "pct_diff": (abs(price - med) / med * 100.0) if med else 0.0,
                    "miner_hotkey": mid,
                })
                try:
                    pct_bps = int(abs(price - med) / med * 10000.0) if med else 0
                    scoring_apply_deviation(out_dir or Path("."), mid, pct_bps)
                    try:
                        from .scoreboard import Scoreboard
                        scb = Scoreboard(out_dir or Path("."))
                        interval = int(os.environ.get("AM_PRICE_INTERVAL_SEC", 60))
                        slot_start = int(pin_dt.timestamp() // max(1, interval)) * max(1, interval)
                        early = (int(pin_dt.timestamp()) - slot_start) <= (max(1, interval) // 2)
                        scb.record_price_sample(mid, ts_str, pct_bps, early)
                    except Exception:
                        pass
                except Exception:
                    pass
                continue
            if stake <= 0:
                continue
            # Apply stake multiplier from scoring
            try:
                mult = scoring_weight_multiplier(out_dir or Path("."), mid)
                # Compose with scoreboard multiplier if present
                mult *= get_multiplier_from_scores(out_dir or Path("."), mid)
            except Exception:
                mult = 1.0
            eff_stake = max(0.0, stake) * max(0.0, float(mult))
            filtered.append((mid, price, eff_stake))
            win_stake_sum += eff_stake
        coverage = win_stake_sum / total_stake
        quorum_meta[netuid] = coverage
        if not filtered:
            prices_out[netuid] = all_time.get(netuid, 0.0)
            continue
        if coverage < quorum_threshold:
            # Not enough stake coverage in window; fallback
            prices_out[netuid] = all_time.get(netuid, 0.0)
            continue
        # Weighted median using remaining samples
        bucket = [WeightedValue(value=price, weight=stake) for (_mid, price, stake) in filtered]
        prices_out[netuid] = aggregate_map_median({netuid: bucket}).get(netuid, all_time.get(netuid, 0.0))
        # staleness = seconds since most recent pin_dt overall (in-window implies small)
        pts = pin_times.get(netuid, [])
        freshest = max(pts) if pts else window_start
        staleness_meta[netuid] = float((now - freshest).total_seconds())

    # Optionally log offenders
    if offenders and out_dir is not None:
        try:
            logp = out_dir / "slashing_log.jsonl"
            with open(logp, "a", encoding="utf-8") as f:
                for entry in offenders:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            # New: Track repeated offenses (three strikes rule)
            track_repeated_offenses(out_dir, offenders)
        except Exception:
            pass

    return prices_out, {int(k): float(v) for k, v in quorum_meta.items()}, {int(k): float(v) for k, v in staleness_meta.items()}


def track_repeated_offenses(out_dir: Path, offenders: List[Dict[str, object]]) -> None:
    """Track historical slashing offenses and apply three-strikes rule."""
    history_path = out_dir / "slashing_history.json"
    try:
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        else:
            history = {}
        for entry in offenders:
            mid = entry["miner_id"]
            history[mid] = history.get(mid, 0) + 1
            if history[mid] >= 3:
                import logging
                logging.warning(f"Miner {mid} has 3+ strikes: triggering deregistration")
                # Add deregistration logic here (e.g., call to protocol function)
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f)
    except Exception:
        import logging
        logging.error("Failed to track repeated offenses")


def _to_bps(weights: Dict[int, float], total_bps: int = 10000) -> Tuple[Dict[int, int], Dict[int, float]]:
    # Largest remainder method with deterministic tie-breaker (higher fractional first, then netuid asc)
    # Normalize weights to sum to 1.0 for robustness
    denom = sum(float(v) for v in weights.values()) or 1.0
    items = sorted(((int(k), float(v) / denom) for k, v in weights.items()), key=lambda kv: (-kv[1], kv[0]))
    floors: Dict[int, int] = {}
    fracs: List[Tuple[float, int]] = []  # (frac, netuid)
    s = 0
    for netuid, w in items:
        raw = w * total_bps
        fl = int(raw)
        floors[netuid] = fl
        fracs.append((raw - fl, netuid))
        s += fl
    rem = max(0, total_bps - s)
    fracs.sort(key=lambda x: (-x[0], x[1]))
    for i in range(rem):
        if i < len(fracs):
            floors[fracs[i][1]] += 1
    # Recompute floats from bps
    weights_float = {n: floors[n] / float(total_bps) for n, _ in items}
    return floors, weights_float


def _day_key(dt: datetime) -> str:
    d = dt.astimezone(timezone.utc).date()
    return d.isoformat()


def _aggregate_daily_emissions_by_day(reports: Iterable[EmissionsReport], out_dir: Optional[Path] = None, max_reports: int = 1000, max_uids_per_report: int = 1000) -> Dict[str, Dict[int, float]]:
    # Build per-day consensus emissions using stake-weighted medians across miners
    # Keep miner identity for filtering and quorum checks
    day_samples: Dict[str, Dict[int, List[Tuple[str, float, float, str]]]] = {}
    
    report_count = 0
    for rep in reports:
        if report_count >= max_reports:
            break
        try:
            rep_dt = _parse_iso8601_z(rep.snapshot_ts)
        except Exception:
            rep_dt = datetime.fromtimestamp(0, tz=timezone.utc)
        dk = _day_key(rep_dt)
        if dk not in day_samples:
            day_samples[dk] = {}
            
        uid_count = 0
        for netuid, val in rep.emissions_by_netuid.items():
            if uid_count >= max_uids_per_report:
                break
            day_samples[dk].setdefault(netuid, []).append((rep.miner_id, float(val), max(0.0, float(rep.stake_tao)), rep.snapshot_ts))
            uid_count += 1
        report_count += 1

    quorum_threshold = float(os.environ.get("AM_EMISSIONS_QUORUM", 0.7))
    band_pct = float(os.environ.get("AM_EMISSIONS_BAND_PCT", 0.5))
    outlier_k = float(os.environ.get("AM_EMISSIONS_MAD_K", 5.0))
    day_to_consensus: Dict[str, Dict[int, float]] = {}
    offenders: List[Dict[str, object]] = []
    for dk, net_map in day_samples.items():
        # Compute total stake for quorum denominator (latest per miner in this day)
        miner_stake_latest: Dict[str, float] = {}
        for arr in net_map.values():
            for (mid, _v, stake, _ts) in arr:
                miner_stake_latest[mid] = stake
        total_stake = sum(miner_stake_latest.values()) or 1.0

        out_map: Dict[int, float] = {}
        for netuid, arr in net_map.items():
            vals = [v for (_mid, v, _s, _ts) in arr]
            if not vals:
                out_map[netuid] = 0.0
                continue
            med = _median(vals)
            mad = _mad(vals, med)
            filtered: List[Tuple[str, float, float]] = []
            covered = 0.0
            for (mid, v, stake, rep_ts) in arr:
                if mad > 0 and abs(v - med) > outlier_k * mad:
                    offenders.append({
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "type": "deviation",
                        "metric": "emissions",
                        "uid": int(netuid),
                        "report_value": float(v),
                        "median": float(med),
                        "pct_diff": (abs(v - med) / med * 100.0) if med else 0.0,
                        "miner_hotkey": mid,
                    })
                    try:
                        pct_bps = int(abs(v - med) / med * 10000.0) if med else 0
                        scoring_apply_deviation(out_dir or Path("."), mid, pct_bps)
                        # Scoreboard: record emission sample with delay/on_time
                        try:
                            scb = Scoreboard(out_dir or Path("."))
                            # snapshot at configured hour UTC
                            snap_hour = int(os.environ.get("AM_SNAPSHOT_HOUR_UTC", 16))
                            rep_dt = _parse_iso8601_z(rep_ts)
                            snap_dt = rep_dt.replace(hour=snap_hour, minute=0, second=0, microsecond=0)
                            delay_sec = max(0, int((rep_dt - snap_dt).total_seconds()))
                            L_MAX = int(os.environ.get("AM_SCORE_L_MAX_SEC", 60))
                            on_time = delay_sec <= L_MAX
                            scb.record_emission_sample(mid, rep_ts, pct_bps, delay_sec, on_time)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    continue
                if med > 0 and abs(v - med) / med > max(0.0, band_pct):
                    offenders.append({
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "type": "deviation",
                        "metric": "emissions",
                        "uid": int(netuid),
                        "report_value": float(v),
                        "median": float(med),
                        "pct_diff": (abs(v - med) / med * 100.0) if med else 0.0,
                        "miner_hotkey": mid,
                    })
                    try:
                        pct_bps = int(abs(v - med) / med * 10000.0) if med else 0
                        scoring_apply_deviation(out_dir or Path("."), mid, pct_bps)
                        try:
                            scb = Scoreboard(out_dir or Path("."))
                            snap_hour = int(os.environ.get("AM_SNAPSHOT_HOUR_UTC", 16))
                            rep_dt = _parse_iso8601_z(rep_ts)
                            snap_dt = rep_dt.replace(hour=snap_hour, minute=0, second=0, microsecond=0)
                            delay_sec = max(0, int((rep_dt - snap_dt).total_seconds()))
                            L_MAX = int(os.environ.get("AM_SCORE_L_MAX_SEC", 60))
                            on_time = delay_sec <= L_MAX
                            scb.record_emission_sample(mid, rep_ts, pct_bps, delay_sec, on_time)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    continue
                if stake <= 0:
                    continue
                # Apply scoring multiplier
                try:
                    mult = scoring_weight_multiplier(out_dir or Path("."), mid)
                    mult *= get_multiplier_from_scores(out_dir or Path("."), mid)
                except Exception:
                    mult = 1.0
                eff = max(0.0, stake) * max(0.0, float(mult))
                filtered.append((mid, v, eff))
                covered += eff
            coverage = covered / total_stake
            if not filtered or coverage < quorum_threshold:
                # Fallback to simple median without weights
                out_map[netuid] = med
            else:
                bucket = [WeightedValue(value=v, weight=st) for (_mid, v, st) in filtered]
                out_map[netuid] = aggregate_map_median({netuid: bucket}).get(netuid, med)
        day_to_consensus[dk] = out_map

    if offenders and out_dir is not None:
        try:
            logp = out_dir / "slashing_log.jsonl"
            with open(logp, "a", encoding="utf-8") as f:
                for entry in offenders:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        except Exception:
            pass
    return day_to_consensus


def persist_emissions_history(out_dir: Path, day_map: Dict[str, Dict[int, float]]) -> None:
    """Append daily consensus emissions to a TSV for audit."""
    try:
        hist = out_dir / "emissions_history.tsv"
        exists = hist.exists()
        with open(hist, "a", encoding="utf-8") as f:
            if not exists:
                f.write("day\tnetuid\temission_tao_per_day\n")
            for day in sorted(day_map.keys()):
                m = day_map[day]
                for n, v in sorted(m.items()):
                    f.write(f"{day}\t{n}\t{v}\n")
    except Exception:
        pass


def _load_json(path: Path) -> Dict[str, any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Lenient fallback: quote bare numeric keys like {2: true} → {"2": true}
        try:
            import re as _re
            raw = path.read_text(encoding="utf-8")
            fixed = _re.sub(r'([\{,\s])(\d+)\s*:', r'\1"\2":', raw)
            return json.loads(fixed)
        except Exception:
            return {}


def _save_json(path: Path, data: Dict[str, any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def _update_first_seen(out_dir: Path, today_key: str, todays_netuids: Iterable[int]) -> None:
    first_seen_path = out_dir / "state" / "emission_first_seen.json"
    first_seen = _load_json(first_seen_path)
    changed = False
    for n in todays_netuids:
        k = str(n)
        if k not in first_seen:
            first_seen[k] = today_key
            changed = True
    if changed:
        _save_json(first_seen_path, first_seen)


def _eligibility_overrides(out_dir: Path) -> Dict[str, bool]:
    raw = _load_json(out_dir / "state" / "eligibility_overrides.json")
    try:
        return {str(k): bool(v) for k, v in raw.items()}
    except Exception:
        return {}


def has_continuous_emissions(out_dir: Path, day_map: Dict[str, Dict[int, float]], uid: int, days: int = 90, allowed_gaps: int = 0) -> bool:
    """Return True if uid has nonzero emissions on each of the last `days` calendar days up to the latest day,
    allowing at most `allowed_gaps` missing/zero days.
    Uses the in-memory day_map built for this aggregation run; does not require history file.
    """
    if not day_map:
        return False
    days_sorted = sorted(day_map.keys())
    last_day = days_sorted[-1]
    # Build the last N distinct day keys (inclusive of last_day)
    window_keys = days_sorted[-days:] if len(days_sorted) >= days else days_sorted
    # Count gaps (missing or zero) for uid across window
    gaps = 0
    for dk in window_keys:
        val = float(day_map.get(dk, {}).get(int(uid), 0.0))
        if val <= 0:
            gaps += 1
            if gaps > max(0, int(allowed_gaps)):
                return False
    # If we had fewer than `days` total keys, require all present days to be nonzero and treat missing as gaps
    if len(window_keys) < days:
        missing = days - len(window_keys)
        if gaps + missing > max(0, int(allowed_gaps)):
            return False
    return True


def _filter_by_eligibility(out_dir: Path, emissions_avg: Dict[int, float], now_dt: datetime, months: int = 3) -> Dict[int, float]:
    """Deprecated: age-based eligibility replaced by continuity check. Kept for compatibility."""
    overrides = _eligibility_overrides(out_dir)
    # Build continuity map from persisted history if available; else default to in-memory during compute
    try:
        hist = _load_json(out_dir / "state" / "eligibility_continuity.json")
    except Exception:
        hist = {}
    eligible: Dict[int, float] = {}
    for netuid, val in emissions_avg.items():
        key = str(netuid)
        if overrides.get(key) is True:
            eligible[netuid] = val
            continue
        ok = bool(hist.get(key, False))
        if ok:
            eligible[netuid] = val
    return eligible


def compute_rolling_emissions(out_dir: Path, reports: List[EmissionsReport]) -> Tuple[Dict[int, float], Dict[int, bool]]:
    # Compute per-day consensus then 14-day rolling averages
    day_map = _aggregate_daily_emissions_by_day(reports, out_dir=out_dir)
    if not day_map:
        return {}, {}
    # Persist daily consensus emissions history
    persist_emissions_history(out_dir, day_map)
    # Seed first_seen using earliest day a net appears if not recorded yet
    try:
        first_seen_path = out_dir / "state" / "emission_first_seen.json"
        first_seen = _load_json(first_seen_path)
        changed = False
        for dk in sorted(day_map.keys()):
            for n in day_map[dk].keys():
                k = str(n)
                if k not in first_seen:
                    first_seen[k] = dk
                    changed = True
        if changed:
            _save_json(first_seen_path, first_seen)
    except Exception:
        pass
    now_dt = datetime.now(timezone.utc)
    # Update first-seen with today's consensus
    today_key = _day_key(now_dt)
    todays = day_map.get(today_key, {})
    if todays:
        _update_first_seen(out_dir, today_key, todays.keys())

    # Collect last 14 distinct day keys up to today
    keys_sorted = sorted(day_map.keys())
    # restrict to keys <= today
    keys_sorted = [k for k in keys_sorted if k <= today_key]
    last_keys = keys_sorted[-14:] if len(keys_sorted) > 14 else keys_sorted
    # Average across days per netuid
    sums: Dict[int, float] = defaultdict(float)
    all_netuids = set()
    for dk in last_keys:
        dm = day_map.get(dk, {})  # Missing day = {}
        all_netuids.update(dm.keys())
        for n in all_netuids:
            sums[n] += float(dm.get(n, 0.0))
    avg: Dict[int, float] = {n: s / 14.0 for n, s in sums.items()}  # Fixed /14, missing=0

    # Compute eligibility map using strict no-gap continuity (>=90 days no zeros), with overrides
    overrides = _eligibility_overrides(out_dir)
    eligibility: Dict[int, bool] = {}
    for netuid, _v in avg.items():
        if overrides.get(netuid) is not None:
            eligibility[netuid] = overrides[netuid]
            continue
        # Strict check: no zero days in last 90
        has_gap = False
        continuous_days = 0
        for dk in sorted(keys_sorted)[-90:]:
            val = day_map.get(dk, {}).get(netuid, 0.0)
            if val > 0:
                continuous_days += 1
            else:
                has_gap = True
                continuous_days = 0  # Reset on gap
        eligibility[netuid] = continuous_days >= 90 and not has_gap

    # Persist current eligibility for monitoring
    try:
        _save_json(out_dir / "state" / "eligibility.json", {str(k): int(v) for k, v in eligibility.items()})
    except Exception:
        pass

    return avg, eligibility


def compute_rolling_emissions_and_weights(out_dir: Path, reports: List[EmissionsReport], top_n: int = 20) -> Tuple[Dict[int, float], Dict[int, float], Dict[int, bool]]:
    avg, eligibility = compute_rolling_emissions(out_dir, reports)
    # Convert to weights by selecting top-N among eligible only, then normalize (with hysteresis)
    from ..tao20.index_design import EmissionStat, select_top_n_by_emission, normalize_weights
    settings = get_settings()
    eligible_avg = {k: v for k, v in avg.items() if eligibility.get(k)}
    ranked_by_emission = sorted(eligible_avg.items(), key=lambda kv: kv[1], reverse=True)
    # Load previous constituents for hysteresis
    prev_constituents: set[int] = set()
    try:
        prev_path = out_dir / "weights.json"
        raw_prev = json.loads(prev_path.read_text(encoding="utf-8"))
        prev_constituents = set(int(k) for k in (raw_prev.get("weights_bps") or {}).keys())
    except Exception:
        prev_constituents = set()
    # Load rank history
    rank_hist_path = out_dir / "rank_history.json"
    try:
        _rank_hist_raw = json.loads(rank_hist_path.read_text(encoding="utf-8"))
        rank_history: Dict[int, int] = {int(k): int(v) for k, v in _rank_hist_raw.items()}
    except Exception:
        rank_history = {}
    top_uids = apply_hysteresis(ranked_by_emission, prev_constituents, rank_history, settings)
    # Update rank history
    current_top = set(top_uids)
    for uid, _e in ranked_by_emission:
        if uid in current_top:
            rank_history[uid] = rank_history.get(uid, 0) + 1
        else:
            if uid in rank_history:
                rank_history[uid] = 0
    try:
        tmp = rank_hist_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({str(k): int(v) for k, v in rank_history.items()}, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        tmp.replace(rank_hist_path)
    except Exception:
        pass
    stats = [EmissionStat(netuid=u, avg_daily_emission_tao=eligible_avg.get(u, 0.0)) for u in top_uids]
    weights = normalize_weights(stats)
    return weights, avg, eligibility


def consensus_nav(nav_reports: List[NavReport]) -> float:
    if not nav_reports:
        return 0.0
    vals = sorted([nr.nav_per_token_tao for nr in nav_reports])
    mid = len(vals) // 2
    return (vals[mid] if len(vals) % 2 == 1 else (vals[mid - 1] + vals[mid]) / 2.0)


def aggregate_and_emit(in_dir: Path, out_file: Path, top_n: int = 20) -> None:
    reps = load_reports(in_dir)
    # Rolling 14-day emissions with 3-month eligibility
    weights, avg_emissions, eligibility = compute_rolling_emissions_and_weights(in_dir, reps, top_n=top_n)
    # Epoch-anchored rebalance gating via deterministic rebalance_id
    rid = current_rebalance_id()
    ok_quorum, failed_subnets = validate_rebalance_quorum(rid, reps)
    if not ok_quorum:
        # Exclude failed subnets from eligible set in this epoch by marking paused
        paused_assets = set(failed_subnets)
        # Optionally, record paused for observability
        try:
            (in_dir / "paused_subnets.json").write_text(json.dumps(sorted(int(u) for u in paused_assets)), encoding="utf-8")
        except (OSError, IOError, json.JSONDecodeError) as e:
            # Expected file I/O errors - log and continue
            import logging
            logging.debug(f"Failed to write paused_subnets.json: {e}")
            pass
        raise ValueError("REB_QUORUM_FAIL")
    # Consensus prices with 30-minute TWAP fallback and outlier filtering; stake-weighted with quorum
    stake_by_miner = build_miner_stake_map(reps)
    price_reports = load_price_reports(in_dir)
    prices, price_quorum, price_staleness = consensus_prices_with_twap(
        price_reports,
        stake_by_miner=stake_by_miner,
        window_minutes=30,
        outlier_k=5.0,
        quorum_threshold=float(os.environ.get("AM_PRICE_QUORUM", 0.33)),
        price_band_pct=float(os.environ.get("AM_PRICE_BAND_PCT", 0.2)),
        stale_sec=int(os.environ.get("AM_PRICE_STALE_SEC", 120)),
        out_dir=in_dir,
    )
    # Simulated vault NAV if we have prices and initial weights
    vault_path = in_dir / "vault_state.json"
    vault = load_vault(vault_path)
    if vault is None and prices and weights:
        vault = initialize_vault(weights, prices)
        save_vault(vault_path, vault)
    sim_nav = compute_nav(prices, vault) if vault else 0.0
    # Build WeightSet epoch info and hash (canonicalized, deterministic)
    eid = current_epoch_id()
    now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Convert to bps and constituents
    # Convert to exact BPS using Decimal-based largest remainder; freeze on zero-sum
    from ..tao20.index_design import to_bps_exact
    if weights:
        bps_map, weights = to_bps_exact(weights)
    else:
        # Freeze to previous epoch's constituents if available
        bps_map = {}
        try:
            prev_path = in_dir / f"weightset_epoch_{eid-1}.json"
            raw_prev = json.loads(prev_path.read_text(encoding="utf-8"))
            prev_const = raw_prev.get("constituents") or []
            assert prev_const, "NO_PREV_WEIGHTS_TO_FREEZE"
            bps_map = {int(c["uid"]): int(c["weight_bps"]) for c in prev_const}
            # Set float weights to match BPS
            weights = {int(k): (int(v) / 10000.0) for k, v in bps_map.items()}
            frozen_zero_sum = True
        except Exception:
            frozen_zero_sum = True
            bps_map, weights = ({}, {})
    constituents = [{"uid": int(k), "weight_bps": int(v), "emissions_14d": float(avg_emissions.get(k, 0.0))} for k, v in sorted(bps_map.items())]
    # Canonical WeightSet v1 container
    ws_obj = {
        "schema_version": "1.0.0",
        "epoch_id": int(eid),
        "as_of_ts": now_ts,
        "weights": {str(k): float(v) for k, v in weights.items()},
        "epoch_index": int(eid),
        "cutover_ts": __import__("subnet.sim.epoch", fromlist=["next_epoch_cutover_ts"]).next_epoch_cutover_ts(),
        "method": "emissions_weighted_14d",
        "eligibility_min_days": 90,
        "constituents": [{"uid": c["uid"], "weight_bps": c["weight_bps"], "emissions_14d": c["emissions_14d"]} for c in constituents],
        "rebalance_id": int(rid),
        "frozen_zero_sum": bool(locals().get("frozen_zero_sum", False)),
        "weights_source": ("previous_snapshot" if locals().get("frozen_zero_sum", False) else "current_snapshot"),
    }
    canon = json.dumps(ws_obj, separators=(",", ":"), sort_keys=True)
    ws_hash = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    # Persist epoch WeightSet alongside
    try:
        epoch_path = in_dir / f"weightset_epoch_{eid}.json"
        epoch_path.write_text(canon, encoding="utf-8")
        # Write sha256 artifact and call publish stub (non-blocking)
        try:
            (in_dir / f"weightset_epoch_{eid}.sha256").write_text(ws_hash + "\n", encoding="utf-8")
        except Exception:
            pass
        try:
            publish_weightset(ws_hash, str(epoch_path))
        except Exception:
            pass
    except Exception:
        pass

    result = {
        "weights": weights,
        "weights_bps": {str(k): int(v) for k, v in bps_map.items()},
        "consensus_prices": prices,
        "sim_nav": sim_nav,
        "emissions_avg_14d": {str(k): float(v) for k, v in avg_emissions.items()},
        "eligibility": {str(k): bool(v) for k, v in eligibility.items()},
        "price_quorum": {str(k): float(v) for k, v in price_quorum.items()},
        "price_staleness_sec": {str(k): float(v) for k, v in price_staleness.items()},
        "epoch_id": int(eid),
        "weightset_hash": ws_hash,
        "rebalance_id": int(rid),
        "paused_subnets": sorted(int(u) for u in (paused_assets if 'paused_assets' in locals() else set())),
    }
    out_file.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    from ..common.settings import get_settings
    settings = get_settings()
    in_dir = Path(settings.in_dir)
    out_file = Path(os.environ.get("AM_WEIGHTSET", str(in_dir / "weights.json")))
    aggregate_and_emit(in_dir, out_file)


if __name__ == "__main__":
    main()


def validate_rebalance_quorum(rebalance_id: int, signed_reports: List[EmissionsReport]) -> Tuple[bool, set[int]]:
    from collections import defaultdict
    settings = get_settings()
    # stake-weighted participation per subnet at the SAME rebalance_id
    stake_total = defaultdict(float)
    stake_on_rid = defaultdict(float)
    failed: set[int] = set()
    for rep in signed_reports:
        try:
            st = float(getattr(rep, "stake_tao", 0.0))
            sid = int(getattr(rep, "subnet_id", 0)) if hasattr(rep, "subnet_id") else 0
            stake_total[sid] += st
            ts = _parse_iso8601_z(getattr(rep, "snapshot_ts", "")).timestamp()
            rid_rep = current_rebalance_id(int(ts))
            if int(rid_rep) == int(rebalance_id):
                stake_on_rid[sid] += st
        except Exception:
            continue
    quorum = float(settings.quorum_stake_pct)
    for sid in stake_total:
        if stake_on_rid.get(sid, 0.0) < quorum * max(1.0, stake_total.get(sid, 0.0)):
            failed.add(int(sid))
    return (len(failed) == 0), failed


def apply_hysteresis(ranked_by_emission: List[Tuple[int, float]], prev_constituents: set[int], rank_history: Dict[int, int], settings) -> List[int]:
    # ranked_by_emission sorted DESC by E14d
    emissions = dict(ranked_by_emission)
    naive = [uid for uid, _ in ranked_by_emission[:20]]
    if not prev_constituents:
        return naive[:20]
    incumbents = [u for u in prev_constituents if u in emissions]
    cutoff_e = min((emissions[u] for u in incumbents), default=None)
    selected: List[int] = []
    for uid, e in ranked_by_emission:
        if len(selected) >= 20:
            break
        if uid in prev_constituents:
            selected.append(uid)
            continue
        if cutoff_e is None:
            selected.append(uid)
            continue
        margin_ok = e >= cutoff_e * (1.0 + float(settings.entry_margin_pct))
        sustain_ok = int(rank_history.get(uid, 0)) >= int(settings.sustain_days)
        if margin_ok or sustain_ok:
            selected.append(uid)
    if len(selected) < 20:
        for uid in naive:
            if uid not in selected:
                selected.append(uid)
                if len(selected) == 20:
                    break
    return selected[:20]


