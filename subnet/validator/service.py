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
from ..common.bt_signing import verify_with_ss58
from ..sim.vault import VaultState, load_vault, save_vault, initialize_vault, compute_nav
from ..sim.epoch import current_epoch_id


def load_reports(in_dir: Path) -> List[EmissionsReport]:
    reports: List[EmissionsReport] = []
    for path in glob.glob(str(in_dir / "emissions_*_*.json")):
        try:
            text = Path(path).read_text(encoding="utf-8")
            rep = EmissionsReport.from_json(text)
            # If signature present and has signer, keep only valid ones
            if rep.signature and rep.signer_ss58:
                ok = verify_with_ss58(text.encode("utf-8"), rep.signature, rep.signer_ss58)
                if not ok:
                    continue
            reports.append(rep)
        except Exception:
            continue
    return reports


def load_price_reports(in_dir: Path) -> List[PriceReport]:
    reps: List[PriceReport] = []
    for path in glob.glob(str(in_dir / "prices_*_*.json")):
        try:
            text = Path(path).read_text(encoding="utf-8")
            pr = PriceReport.from_json(text)
            if pr.signature and pr.signer_ss58:
                ok = verify_with_ss58(text.encode("utf-8"), pr.signature, pr.signer_ss58)
                if not ok:
                    continue
            reps.append(pr)
        except Exception:
            continue
    return reps


def load_nav_reports(in_dir: Path) -> List[NavReport]:
    reps: List[NavReport] = []
    for path in glob.glob(str(in_dir / "nav_*_*.json")):
        try:
            text = Path(path).read_text(encoding="utf-8")
            nr = NavReport.from_json(text)
            if nr.signature and nr.signer_ss58:
                ok = verify_with_ss58(text.encode("utf-8"), nr.signature, nr.signer_ss58)
                if not ok:
                    continue
            reps.append(nr)
        except Exception:
            continue
    return reps


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


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    mid = len(vs) // 2
    return vs[mid] if len(vs) % 2 == 1 else (vs[mid - 1] + vs[mid]) / 2.0


def _mad(values: List[float], med: float) -> float:
    if not values:
        return 0.0
    deviations = [abs(v - med) for v in values]
    return _median(deviations)


def build_miner_stake_map(emission_reports: List[EmissionsReport]) -> Dict[str, float]:
    # Use the latest report per miner as their stake weight
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
    quorum_threshold: float = 0.33,
    price_band_pct: float = 0.2,
    stale_sec: int = 120,
    out_dir: Optional[Path] = None,
) -> Tuple[Dict[int, float], Dict[int, float], Dict[int, float]]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    # Collect samples
    samples: Dict[int, List[Tuple[str, float, float, bool]]] = {}
    pin_times: Dict[int, List[datetime]] = {}
    # tuple: (miner_id, price, stake, in_window)
    for rep in price_reports:
        rep_dt = _parse_iso8601_z(rep.ts)
        # Prefer block_time if present for windowing
        pin_dt = _parse_iso8601_z(getattr(rep, "block_time", "")) if getattr(rep, "block_time", "") else rep_dt
        is_stale = (now - pin_dt) > timedelta(seconds=max(0, int(stale_sec)))
        in_win = (pin_dt >= window_start) and not is_stale
        miner_stake = float(stake_by_miner.get(rep.miner_id, 0.0))
        for netuid, price in rep.prices_by_netuid.items():
            samples.setdefault(netuid, []).append((rep.miner_id, float(price), miner_stake, in_win))
            pin_times.setdefault(netuid, []).append(pin_dt)
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
        for (_mid, price, stake, _in_win) in arr:
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
        win_vals = [price for (_mid, price, _stake, in_win) in arr if in_win]
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
        for (mid, price, stake, in_win) in arr:
            if not in_win:
                continue
            if mad > 0 and abs(price - med) > outlier_k * mad:
                offenders.append({"type": "price_outlier", "netuid": netuid, "miner_id": mid, "price": price, "median": med, "mad": mad})
                continue
            # Enforce band relative to median (e.g., 20%)
            if med > 0 and abs(price - med) / med > max(0.0, price_band_pct):
                offenders.append({"type": "price_band_violation", "netuid": netuid, "miner_id": mid, "price": price, "median": med, "band_pct": price_band_pct})
                continue
            if stake <= 0:
                continue
            filtered.append((mid, price, stake))
            win_stake_sum += stake
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
                    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        except Exception:
            pass

    return prices_out, {int(k): float(v) for k, v in quorum_meta.items()}, {int(k): float(v) for k, v in staleness_meta.items()}


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


def _aggregate_daily_emissions_by_day(reports: Iterable[EmissionsReport], out_dir: Optional[Path] = None) -> Dict[str, Dict[int, float]]:
    # Build per-day consensus emissions using stake-weighted medians across miners
    # Keep miner identity for filtering and quorum checks
    day_samples: Dict[str, Dict[int, List[Tuple[str, float, float]]]] = {}
    for rep in reports:
        try:
            rep_dt = _parse_iso8601_z(rep.snapshot_ts)
        except Exception:
            rep_dt = datetime.fromtimestamp(0, tz=timezone.utc)
        dk = _day_key(rep_dt)
        if dk not in day_samples:
            day_samples[dk] = {}
        for netuid, val in rep.emissions_by_netuid.items():
            day_samples[dk].setdefault(netuid, []).append((rep.miner_id, float(val), max(0.0, float(rep.stake_tao))))

    quorum_threshold = float(os.environ.get("AM_EMISSIONS_QUORUM", 0.33))
    band_pct = float(os.environ.get("AM_EMISSIONS_BAND_PCT", 0.5))
    outlier_k = float(os.environ.get("AM_EMISSIONS_MAD_K", 5.0))
    day_to_consensus: Dict[str, Dict[int, float]] = {}
    offenders: List[Dict[str, object]] = []
    for dk, net_map in day_samples.items():
        # Compute total stake for quorum denominator (latest per miner in this day)
        miner_stake_latest: Dict[str, float] = {}
        for arr in net_map.values():
            for (mid, _v, stake) in arr:
                miner_stake_latest[mid] = stake
        total_stake = sum(miner_stake_latest.values()) or 1.0

        out_map: Dict[int, float] = {}
        for netuid, arr in net_map.items():
            vals = [v for (_mid, v, _s) in arr]
            if not vals:
                out_map[netuid] = 0.0
                continue
            med = _median(vals)
            mad = _mad(vals, med)
            filtered: List[Tuple[str, float, float]] = []
            covered = 0.0
            for (mid, v, stake) in arr:
                if mad > 0 and abs(v - med) > outlier_k * mad:
                    offenders.append({"type": "emission_outlier", "day": dk, "netuid": netuid, "miner_id": mid, "value": v, "median": med, "mad": mad})
                    continue
                if med > 0 and abs(v - med) / med > max(0.0, band_pct):
                    offenders.append({"type": "emission_band_violation", "day": dk, "netuid": netuid, "miner_id": mid, "value": v, "median": med, "band_pct": band_pct})
                    continue
                if stake <= 0:
                    continue
                filtered.append((mid, v, stake))
                covered += stake
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
                    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
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
    return _load_json(out_dir / "state" / "eligibility_overrides.json")


def _filter_by_eligibility(out_dir: Path, emissions_avg: Dict[int, float], now_dt: datetime, months: int = 3) -> Dict[int, float]:
    first_seen = _load_json(out_dir / "state" / "emission_first_seen.json")
    overrides = _eligibility_overrides(out_dir)
    min_age_days = int(30 * months)
    eligible: Dict[int, float] = {}
    for netuid, val in emissions_avg.items():
        key = str(netuid)
        if overrides.get(key) is True:
            eligible[netuid] = val
            continue
        ts = first_seen.get(key)
        if not ts:
            # Not seen before; skip until recorded and ages in subsequent runs
            continue
        try:
            first_dt = _parse_iso8601_z(ts)
        except Exception:
            continue
        age_days = (now_dt - first_dt).days
        if age_days >= min_age_days:
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
    counts: Dict[int, int] = defaultdict(int)
    for dk in last_keys:
        dm = day_map.get(dk, {})
        for n, v in dm.items():
            sums[n] += float(v)
            counts[n] += 1
    avg: Dict[int, float] = {}
    for n, s in sums.items():
        c = counts.get(n, 0) or 1
        avg[n] = s / float(c)

    # Compute eligibility map and also provide filtered averages for weighting
    first_seen = _load_json(out_dir / "state" / "emission_first_seen.json")
    overrides = _eligibility_overrides(out_dir)
    min_age_days = int(30 * 3)
    eligibility: Dict[int, bool] = {}
    for netuid, _v in avg.items():
        key = str(netuid)
        if overrides.get(key) is True:
            eligibility[netuid] = True
            continue
        ts = first_seen.get(key)
        if not ts:
            eligibility[netuid] = False
            continue
        try:
            first_dt = _parse_iso8601_z(ts)
        except Exception:
            eligibility[netuid] = False
            continue
        eligibility[netuid] = ((now_dt - first_dt).days >= min_age_days)

    return avg, eligibility


def compute_rolling_emissions_and_weights(out_dir: Path, reports: List[EmissionsReport], top_n: int = 20) -> Tuple[Dict[int, float], Dict[int, float], Dict[int, bool]]:
    avg, eligibility = compute_rolling_emissions(out_dir, reports)
    # Convert to weights by selecting top-N among eligible only, then normalize
    from ..tao20.index_design import EmissionStat, select_top_n_by_emission, normalize_weights
    eligible_avg = {k: v for k, v in avg.items() if eligibility.get(k)}
    stats = [EmissionStat(netuid=k, avg_daily_emission_tao=v) for k, v in eligible_avg.items()]
    top = select_top_n_by_emission(stats, n=top_n)
    weights = normalize_weights(top)
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
    # Consensus prices with 30-minute TWAP fallback and outlier filtering; stake-weighted with quorum
    stake_by_miner = build_miner_stake_map(reps)
    prices, price_quorum, price_staleness = consensus_prices_with_twap(
        load_price_reports(in_dir),
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
    # Build WeightSet epoch info and hash
    eid = current_epoch_id()
    now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ws_obj = {
        "epoch_id": int(eid),
        "as_of_ts": now_ts,
        "weights": {str(k): float(v) for k, v in weights.items()},
    }
    canon = json.dumps(ws_obj, separators=(",", ":"), sort_keys=True)
    ws_hash = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    # Persist epoch WeightSet alongside
    try:
        (in_dir / f"weightset_epoch_{eid}.json").write_text(json.dumps(ws_obj, separators=(",", ":")), encoding="utf-8")
    except Exception:
        pass

    # Enforce exactly top-N and renormalize
    if weights:
        items = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        if top_n and top_n > 0:
            items = items[:top_n]
        denom = sum(w for _, w in items) or 1.0
        weights = {k: (w / denom) for k, w in items}

    bps_map, weights = _to_bps(weights) if weights else ({}, {})

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
    }
    out_file.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    in_dir = Path(os.environ.get("AM_IN_DIR", "/Users/alexanderlange/alphamind/subnet/out"))
    out_file = Path(os.environ.get("AM_WEIGHTSET", "/Users/alexanderlange/alphamind/subnet/out/weights.json"))
    aggregate_and_emit(in_dir, out_file)


if __name__ == "__main__":
    main()


