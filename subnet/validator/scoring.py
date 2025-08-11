#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any
from .slashing import slash_miner


def _state_dir(base: Path) -> Path:
    p = base / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _scores_path(base: Path) -> Path:
    return _state_dir(base) / "miner_scores.json"


def _now_iso() -> str:
    return datetime.strftime(datetime.now(timezone.utc), "%Y-%m-%dT%H:%M:%SZ")


def load_scores(base: Path) -> Dict[str, Any]:
    try:
        return json.loads(_scores_path(base).read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_scores(base: Path, data: Dict[str, Any]) -> None:
    _scores_path(base).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def _ensure_entry(data: Dict[str, Any], hotkey: str) -> Dict[str, Any]:
    if hotkey not in data:
        data[hotkey] = {"score": 1.0, "strikes": 0, "suspended": False, "last_update": _now_iso()}
    # Decay score back toward 1.0
    entry = data[hotkey]
    last_update = datetime.fromisoformat(entry.get("last_update", _now_iso()))
    now = datetime.now(timezone.utc)
    hours_since_update = (now - last_update).total_seconds() / 3600
    # Decay factor: regain 10% of lost score per 24h
    decay_rate_per_hour = 0.1 / 24
    current_score = float(entry.get("score", 1.0))
    recovered_score = (1.0 - current_score) * (1.0 - (1.0 - decay_rate_per_hour) ** hours_since_update)
    entry["score"] = min(1.0, current_score + recovered_score)
    entry["last_update"] = now.isoformat()
    return entry


def apply_deviation(base: Path, hotkey: str, pct_diff_bps: int) -> None:
    try:
        soft = int(os.environ.get("AM_SLASH_SOFT_THRESH_BPS", 500))
        hard = int(os.environ.get("AM_SLASH_HARD_THRESH_BPS", 1000))
        suspend = int(os.environ.get("AM_STRIKES_SUSPEND", 3))
        max_penalty = float(os.environ.get("AM_MAX_SCORE_PENALTY", 0.5))  # Cap at 50% penalty
    except Exception:
        soft, hard, suspend = 500, 1000, 3
        max_penalty = 0.5
    if not hotkey:
        return
    data = load_scores(base)
    ent = _ensure_entry(data, hotkey)
    
    # Progressive penalty based on severity
    current_score = float(ent.get("score", 1.0))
    if pct_diff_bps >= hard:
        ent["strikes"] = int(ent.get("strikes", 0)) + 1
        penalty = min(0.2, max_penalty)  # Cap penalty
        ent["score"] = max(0.0, current_score - penalty)
        ent["last_hard_violation"] = _now_iso()
        slash_miner(hotkey, 0.10)  # 10% slash for major violation
    elif pct_diff_bps >= soft:
        penalty = min(0.05, max_penalty * 0.25)  # Smaller penalty for soft violations
        ent["score"] = max(0.0, current_score - penalty)
        ent["last_soft_violation"] = _now_iso()
        slash_miner(hotkey, 0.05)  # 5% slash for minor violation
    
    # Enhanced suspension logic with time decay
    strikes = int(ent.get("strikes", 0))
    if strikes >= suspend:
        ent["suspended"] = True
        ent["suspension_ts"] = _now_iso()
    
    ent["last_update"] = _now_iso()
    ent["total_violations"] = int(ent.get("total_violations", 0)) + 1
    save_scores(base, data)


def unsuspend_miner(base: Path, hotkey: str) -> None:
    if not hotkey:
        return
    data = load_scores(base)
    ent = data.get(hotkey)
    if ent and ent.get("suspended"):
        ent["suspended"] = False
        ent["strikes"] = 0  # Reset strikes after suspension
        ent["last_update"] = _now_iso()
        save_scores(base, data)


def weight_multiplier(base: Path, hotkey: str) -> float:
    if not hotkey:
        return 1.0
    data = load_scores(base)
    ent = data.get(hotkey)
    if not ent:
        return 1.0
    # Map score∈[0,1] → [0.5,1.0]
    score = max(0.0, min(1.0, float(ent.get("score", 1.0))))
    return 0.5 + 0.5 * score


def is_suspended(base: Path, hotkey: str) -> bool:
    if not hotkey:
        return False
    data = load_scores(base)
    ent = data.get(hotkey)
    if not ent:
        return False

    if ent.get("suspended"):
        suspension_ts_str = ent.get("suspension_ts")
        if suspension_ts_str:
            suspension_ts = datetime.fromisoformat(suspension_ts_str)
            if datetime.now(timezone.utc) - suspension_ts > timedelta(days=7):
                unsuspend_miner(base, hotkey)
                return False
        return True
    return False


