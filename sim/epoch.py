#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

REBALANCE_PERIOD_SECS = 20 * 24 * 60 * 60  # 20 days (changed from 14 days)
# Freeze a canonical anchor for rebalances (example: 2024-08-14 00:00:00 UTC)
EPOCH_ANCHOR_UNIX = 1_723_593_600


def current_epoch_id(now_unix: Optional[int] = None) -> int:
    if now_unix is None:
        now_unix = int(time.time())
    return max(0, (now_unix - EPOCH_ANCHOR_UNIX) // REBALANCE_PERIOD_SECS)


def next_epoch_cutover_ts(now_unix: Optional[int] = None) -> str:
    """Return ISO8601Z timestamp for next epoch boundary after now.
    Non-breaking helper; used by API/dashboard later.
    """
    if now_unix is None:
        now_unix = int(time.time())
    idx = current_epoch_id(now_unix)
    # end time of current epoch = start + (idx+1)*REBALANCE_PERIOD_SECS
    cut = EPOCH_ANCHOR_UNIX + (idx + 1) * REBALANCE_PERIOD_SECS
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(cut))


def current_epoch_index(now_unix: Optional[int] = None) -> int:
    return current_epoch_id(now_unix)


def current_rebalance_id(now_unix: Optional[int] = None) -> int:
    """Return deterministic rebalance id using fixed anchor + 14d period.
    This avoids wall-clock drift by relying on a frozen epoch anchor.
    """
    if now_unix is None:
        now_unix = int(time.time())
    delta = max(0, now_unix - EPOCH_ANCHOR_UNIX)
    return delta // REBALANCE_PERIOD_SECS


@dataclass
class EpochState:
    epoch_id: int
    last_aggregation_ts: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @staticmethod
    def from_file(path: Path) -> Optional["EpochState"]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return EpochState(epoch_id=int(raw.get("epoch_id", 0)), last_aggregation_ts=str(raw.get("last_aggregation_ts", "")))
        except Exception:
            return None


