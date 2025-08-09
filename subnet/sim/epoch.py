#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

EPOCH_SECONDS = 14 * 24 * 60 * 60  # 14 days
# Anchor epoch start (UTC). You can change this to Bittensor rotation anchor if needed.
ANCHOR_UNIX = 1_700_000_000


def current_epoch_id(now_unix: Optional[int] = None) -> int:
    if now_unix is None:
        now_unix = int(time.time())
    return max(0, (now_unix - ANCHOR_UNIX) // EPOCH_SECONDS)


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


