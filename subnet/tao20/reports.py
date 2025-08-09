#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Any
import json


@dataclass(frozen=True)
class PriceReport:
    ts: str
    prices_by_netuid: Dict[int, float]
    miner_id: str
    # Optional block metadata for pinned reads
    block: int = 0
    block_time: str = ""
    signature: str = ""
    signer_ss58: str = ""

    def to_json(self) -> str:
        data: Dict[str, Any] = asdict(self)
        data["prices_by_netuid"] = {str(k): v for k, v in self.prices_by_netuid.items()}
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "PriceReport":
        raw: Dict[str, Any] = json.loads(text)
        prices = {int(k): float(v) for k, v in raw.get("prices_by_netuid", {}).items()}
        return PriceReport(
            ts=str(raw.get("ts")),
            prices_by_netuid=prices,
            miner_id=str(raw.get("miner_id", "")),
            block=int(raw.get("block", 0) or 0),
            block_time=str(raw.get("block_time", "")),
            signature=str(raw.get("signature", "")),
            signer_ss58=str(raw.get("signer_ss58", "")),
        )


@dataclass(frozen=True)
class NavReport:
    ts: str
    nav_per_token_tao: float
    total_supply: float
    miner_id: str
    signature: str = ""
    signer_ss58: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "NavReport":
        raw: Dict[str, Any] = json.loads(text)
        return NavReport(
            ts=str(raw.get("ts")),
            nav_per_token_tao=float(raw.get("nav_per_token_tao", 0.0)),
            total_supply=float(raw.get("total_supply", 0.0)),
            miner_id=str(raw.get("miner_id", "")),
            signature=str(raw.get("signature", "")),
            signer_ss58=str(raw.get("signer_ss58", "")),
        )


