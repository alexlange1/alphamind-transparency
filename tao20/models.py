#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Any, List, Optional, TypedDict
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
    # v1 scaffold fields (non-breaking):
    schema_version: str = "1.0.0"
    epoch_day: int = 0
    miner_hotkey: str = ""
    sig_scheme: str = ""

    def to_json(self) -> str:
        data: Dict[str, Any] = asdict(self)
        # Convert int keys to str for JSON
        data["emissions_by_netuid"] = {str(k): v for k, v in self.emissions_by_netuid.items()}
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "EmissionsReport":
        raw: Dict[str, Any] = json.loads(text)
        # Accept v1 schema: {"emissions":[{"uid":..,"emissions_tao":..},...]}
        emissions: Dict[int, float] = {}
        if isinstance(raw.get("emissions"), list):
            for ent in raw.get("emissions", []) or []:
                try:
                    uid = int(ent.get("uid"))
                    val = float(ent.get("emissions_tao", 0.0))
                    emissions[uid] = val
                except Exception:
                    continue
        else:
            emissions = {int(k): float(v) for k, v in raw.get("emissions_by_netuid", {}).items()}
        return EmissionsReport(
            snapshot_ts=str(raw.get("snapshot_ts")),
            emissions_by_netuid=emissions,
            miner_id=str(raw.get("miner_id", raw.get("miner_hotkey", ""))),
            stake_tao=float(raw.get("stake_tao", 0.0)),
            signature=str(raw.get("signature", "")),
            signer_ss58=str(raw.get("signer_ss58", raw.get("miner_hotkey", ""))),
            schema_version=str(raw.get("schema_version", "1.0.0")),
            epoch_day=int(raw.get("epoch_day", 0) or 0),
            miner_hotkey=str(raw.get("miner_hotkey", "")),
            sig_scheme=str(raw.get("sig_scheme", "")),
        )


@dataclass(frozen=True)
class WeightSet:
    # Epoch identifier and timestamp when weights were fixed
    epoch_id: int
    as_of_ts: str
    # Finalized weights for the epoch (netuid -> weight)
    weights: Dict[int, float]
    # v1 schema finalized
    schema_version: str = "1.0.0"
    epoch_index: int = 0
    cutover_ts: str = ""
    method: str = "emissions_weighted_14d"
    eligibility_min_days: int = 90
    # Optional canonical constituents published form
    constituents_bps: Optional[Dict[int, int]] = None

    def to_json(self) -> str:
        data: Dict[str, Any] = asdict(self)
        data["weights"] = {str(k): float(v) for k, v in self.weights.items()}
        if data.get("constituents_bps") is not None:
            data["constituents_bps"] = {str(k): int(v) for k, v in (self.constituents_bps or {}).items()}
        return json.dumps(data, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def from_json(text: str) -> "WeightSet":
        raw: Dict[str, Any] = json.loads(text)
        weights = {int(k): float(v) for k, v in raw.get("weights", {}).items()}
        const = raw.get("constituents_bps") or None
        if isinstance(const, dict):
            try:
                const = {int(k): int(v) for k, v in const.items()}
            except Exception:
                const = None
        else:
            const = None
        return WeightSet(
            epoch_id=int(raw.get("epoch_id", 0)),
            as_of_ts=str(raw.get("as_of_ts", "")),
            weights=weights,
            schema_version=str(raw.get("schema_version", "1.0.0")),
            epoch_index=int(raw.get("epoch_index", raw.get("epoch_id", 0) or 0)),
            cutover_ts=str(raw.get("cutover_ts", "")),
            method=str(raw.get("method", "emissions_weighted_14d")),
            eligibility_min_days=int(raw.get("eligibility_min_days", 90)),
            constituents_bps=const,
        )


