#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Set


def _state_dir(base: Path) -> Path:
    p = base / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _paused_path(base: Path) -> Path:
    return _state_dir(base) / "paused_tokens.json"


def load_paused(base: Path) -> Set[int]:
    try:
        data = json.loads(_paused_path(base).read_text(encoding="utf-8"))
        return {int(k) for k, v in data.items() if bool(v)}
    except Exception:
        return set()


def save_paused(base: Path, paused: Set[int]) -> None:
    mp = {str(int(k)): True for k in paused}
    _paused_path(base).write_text(json.dumps(mp, separators=(",", ":")), encoding="utf-8")


def pause(base: Path, uid: int) -> None:
    s = load_paused(base)
    s.add(int(uid))
    save_paused(base, s)


def resume(base: Path, uid: int) -> None:
    s = load_paused(base)
    if int(uid) in s:
        s.remove(int(uid))
    save_paused(base, s)


def is_paused(base: Path, uid: int) -> bool:
    return int(uid) in load_paused(base)


