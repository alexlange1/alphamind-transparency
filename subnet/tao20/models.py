#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Any
import json


@dataclass(frozen=True)
class EmissionsReport:
    # ISO8601 UTC timestamp for snapshot
    snapshot_ts: str
    # avg daily TAO emissions per subnet over 14d window (or latest daily)
    emissions_by_netuid: Dict[int, float]
    # miner identity and stake at time of report (simplified)
    miner_id: str
    stake_tao: float
    # optional bittensor hotkey signature
    signature: str = ""
    signer_ss58: str = ""

    def to_json(self) -> str:
        data: Dict[str, Any] = asdict(self)
        # Convert int keys to str for JSON
        data["emissions_by_netuid"] = {str(k): v for k, v in self.emissions_by_netuid.items()}
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "EmissionsReport":
        raw: Dict[str, Any] = json.loads(text)
        emissions = {int(k): float(v) for k, v in raw.get("emissions_by_netuid", {}).items()}
        return EmissionsReport(
            snapshot_ts=str(raw.get("snapshot_ts")),
            emissions_by_netuid=emissions,
            miner_id=str(raw.get("miner_id", "")),
            stake_tao=float(raw.get("stake_tao", 0.0)),
            signature=str(raw.get("signature", "")),
            signer_ss58=str(raw.get("signer_ss58", "")),
        )


@dataclass(frozen=True)
class WeightSet:
    # Epoch identifier and timestamp when weights were fixed
    epoch_id: int
    as_of_ts: str
    # Finalized weights for the epoch (netuid -> weight)
    weights: Dict[int, float]

    def to_json(self) -> str:
        data: Dict[str, Any] = asdict(self)
        data["weights"] = {str(k): float(v) for k, v in self.weights.items()}
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "WeightSet":
        raw: Dict[str, Any] = json.loads(text)
        weights = {int(k): float(v) for k, v in raw.get("weights", {}).items()}
        return WeightSet(
            epoch_id=int(raw.get("epoch_id", 0)),
            as_of_ts=str(raw.get("as_of_ts", "")),
            weights=weights,
        )


