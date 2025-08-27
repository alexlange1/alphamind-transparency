#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Any, List, Optional
import json


@dataclass(frozen=True)
class PriceItem:
    uid: int
    token: str = ""
    price_in_tao: float = 0.0
    pool_reserve_token: Optional[str] = None
    pool_reserve_tao: Optional[str] = None
    block: Optional[int] = None
    block_time: Optional[str] = None
    pin_source: str = "btcli"


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
    # v1 scaffold fields (non-breaking):
    schema_version: str = "1.0.0"
    prices: Optional[List[PriceItem]] = None

    def to_json(self) -> str:
        data: Dict[str, Any] = asdict(self)
        data["prices_by_netuid"] = {str(k): v for k, v in self.prices_by_netuid.items()}
        if data.get("prices"):
            data["prices"] = [asdict(p) for p in (self.prices or [])]
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "PriceReport":
        raw: Dict[str, Any] = json.loads(text)
        prices = {int(k): float(v) for k, v in raw.get("prices_by_netuid", {}).items()}
        items: Optional[List[PriceItem]] = None
        if isinstance(raw.get("prices"), list):
            try:
                items = [PriceItem(**{
                    "uid": int(x.get("uid")),
                    "token": str(x.get("token", "")),
                    "price_in_tao": float(x.get("price_in_tao", 0.0)),
                    "pool_reserve_token": x.get("pool_reserve_token"),
                    "pool_reserve_tao": x.get("pool_reserve_tao"),
                    "block": (int(x.get("block")) if x.get("block") is not None else None),
                    "block_time": (str(x.get("block_time")) if x.get("block_time") is not None else None),
                    "pin_source": str(x.get("pin_source", "btcli")),
                }) for x in raw.get("prices", [])]
            except Exception:
                items = None
        return PriceReport(
            ts=str(raw.get("ts")),
            prices_by_netuid=prices,
            miner_id=str(raw.get("miner_id", "")),
            block=int(raw.get("block", 0) or 0),
            block_time=str(raw.get("block_time", "")),
            signature=str(raw.get("signature", "")),
            signer_ss58=str(raw.get("signer_ss58", "")),
            schema_version=str(raw.get("schema_version", "1.0.0")),
            prices=items,
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


