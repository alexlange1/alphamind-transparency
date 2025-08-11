#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


def _state_dir(base: Path) -> Path:
    p = base / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _samples_path(base: Path) -> Path:
    return _state_dir(base) / "miner_score_samples.json"


def _scores_path(base: Path) -> Path:
    return _state_dir(base) / "miner_scores.json"


def _history_path(base: Path) -> Path:
    return _state_dir(base) / "miner_history.jsonl"


def _now_iso() -> str:
    return datetime.strftime(datetime.now(timezone.utc), "%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> datetime:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


class Scoreboard:
    def __init__(self, base: Path):
        self.base = base
        self.samples: Dict[str, Dict[str, List[Dict[str, Any]]]] = self._load_samples()

    def _load_samples(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        try:
            return json.loads(_samples_path(self.base).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_samples(self) -> None:
        _samples_path(self.base).write_text(json.dumps(self.samples, separators=(",", ":")), encoding="utf-8")

    def _trim_windows(self) -> None:
        now = datetime.now(timezone.utc)
        # emissions: 14 days; prices: 24h
        for hk, buckets in list(self.samples.items()):
            ems = buckets.get("emissions", [])
            prs = buckets.get("prices", [])
            self.samples.setdefault(hk, {})
            self.samples[hk]["emissions"] = [s for s in ems if (_parse_iso(s.get("ts", "")).replace(tzinfo=timezone.utc) >= now - timedelta(days=14))]
            self.samples[hk]["prices"] = [s for s in prs if (_parse_iso(s.get("ts", "")).replace(tzinfo=timezone.utc) >= now - timedelta(hours=24))]

    def record_emission_sample(self, hotkey: str, ts_iso: str, dev_bps: int, delay_sec: int, on_time: bool) -> None:
        if not hotkey:
            return
        b = self.samples.setdefault(hotkey, {})
        arr = b.setdefault("emissions", [])
        arr.append({"ts": ts_iso, "dev_bps": int(dev_bps), "delay_sec": int(delay_sec), "on_time": bool(on_time)})
        self._trim_windows()
        self._save_samples()

    def record_price_sample(self, hotkey: str, ts_iso: str, dev_bps: int, early: bool) -> None:
        if not hotkey:
            return
        b = self.samples.setdefault(hotkey, {})
        arr = b.setdefault("prices", [])
        arr.append({"ts": ts_iso, "dev_bps": int(dev_bps), "early": bool(early)})
        self._trim_windows()
        self._save_samples()

    def _load_existing_scores(self) -> Dict[str, Any]:
        try:
            return json.loads(_scores_path(self.base).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def finalize_daily(self, now_iso: Optional[str] = None) -> None:
        now = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
        A_MAX = int(os.environ.get("AM_SCORE_A_MAX_BPS", 200))
        L_MAX = int(os.environ.get("AM_SCORE_L_MAX_SEC", 60))
        alpha = float(os.environ.get("AM_SCORE_TRUST_ALPHA", 0.1))
        price_interval = int(os.environ.get("AM_PRICE_INTERVAL_SEC", 60))

        prev = self._load_existing_scores()
        out: Dict[str, Any] = {}
        for hk, buckets in self.samples.items():
            ems = buckets.get("emissions", [])
            prs = buckets.get("prices", [])
            # Accuracy
            def acc_of(samples: List[Dict[str, Any]]) -> float:
                if not samples:
                    return 1.0
                vals = []
                for s in samples:
                    d = abs(int(s.get("dev_bps", 0)))
                    vals.append(max(0.0, 1.0 - (d / max(1, A_MAX))))
                return sum(vals) / float(len(vals))
            acc_em = acc_of(ems)
            acc_pr = acc_of(prs)
            # Uptime
            # Emissions expected 14 submissions in window; prices expected 24h / interval
            em_on = sum(1 for s in ems if bool(s.get("on_time", False)))
            em_req = 14
            pr_on = len(prs)  # assume all present are on-time sample set
            pr_req = max(1, int(24 * 3600 / max(1, price_interval)))
            uptime = min(1.0, (em_on / float(em_req)) * 0.5 + (pr_on / float(pr_req)) * 0.5)
            # Latency
            # Emissions: use delay_sec vs L_MAX if present
            if ems:
                lat_vals = [max(0.0, 1.0 - (int(s.get("delay_sec", 0)) / max(1, L_MAX))) for s in ems]
                lat_em = sum(lat_vals) / float(len(lat_vals))
            else:
                lat_em = 1.0
            # Prices: early True counts as 1, else 0.5 to avoid harshness
            if prs:
                lat_pr = sum(1.0 if bool(s.get("early", False)) else 0.5 for s in prs) / float(len(prs))
            else:
                lat_pr = 1.0
            latency = 0.5 * lat_em + 0.5 * lat_pr
            # Trust
            prev_ent = prev.get(hk) or {}
            prev_trust = float(prev_ent.get("trust", 1.0))
            prev_score = float(prev_ent.get("score", 1.0))
            # Compose components into total (no trust yet)
            accuracy = 0.5 * acc_em + 0.5 * acc_pr
            # total without trust for ewma update
            prelim_total = 0.50 * accuracy + 0.25 * uptime + 0.15 * latency + 0.10 * prev_trust
            trust = (1.0 - alpha) * prev_trust + alpha * prelim_total
            total_unclamped = 0.50 * accuracy + 0.25 * uptime + 0.15 * latency + 0.10 * trust
            # Clamp day-to-day delta to ±0.2 for stability
            delta = total_unclamped - prev_score
            if delta > 0.2:
                total_unclamped = prev_score + 0.2
            elif delta < -0.2:
                total_unclamped = prev_score - 0.2
            total = max(0.0, min(1.0, total_unclamped))
            out[hk] = {
                "score": total,
                "accuracy": accuracy,
                "uptime": uptime,
                "latency": latency,
                "trust": trust,
                "strikes": int(prev_ent.get("strikes", 0)),
                "suspended": bool(prev_ent.get("suspended", False)),
                "samples": {"prices": len(prs), "emissions": len(ems)},
                "last_update": _now_iso(),
            }
        _scores_path(self.base).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
        # Append to history (once per day)
        try:
            with open(_history_path(self.base), "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": _now_iso(), "scores": out}, separators=(",", ":")) + "\n")
        except Exception:
            pass

    def get_scores(self) -> Dict[str, Any]:
        try:
            return json.loads(_scores_path(self.base).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get_multiplier(self, hotkey: str) -> float:
        s = self.get_scores().get(hotkey)
        if not s:
            return 1.0
        sc = max(0.0, min(1.0, float(s.get("score", 1.0))))
        return 0.5 + 0.5 * sc


def get_multiplier_from_scores(base: Path, hotkey: str) -> float:
    try:
        data = json.loads(_scores_path(base).read_text(encoding="utf-8"))
        ent = (data.get(hotkey) or {})
        sc = max(0.0, min(1.0, float(ent.get("score", 1.0))))
        # Coverage guard: require warmup before full weight
        samples = ent.get("samples") or {}
        pr_n = int(samples.get("prices", 0) or 0)
        em_n = int(samples.get("emissions", 0) or 0)
        if pr_n == 0 and em_n == 0:
            sample_factor = 1.0  # no data yet → don't penalize in tests/boot
        else:
            sample_factor = min(1.0, pr_n / 500.0) * min(1.0, em_n / 7.0)
        mult = (0.5 + 0.5 * sc) * sample_factor
        return max(0.5, float(mult))
    except Exception:
        return 1.0


