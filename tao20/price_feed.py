#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Dict, Optional, List, TYPE_CHECKING, Tuple
import os
import json


@dataclass(frozen=True)
class PriceSnapshot:
    # TAO-denominated prices by netuid
    prices_by_netuid: Dict[int, float]


def parse_btcli_table(text: str) -> Dict[int, float]:
    prices: Dict[int, float] = {}
    for line in text.splitlines():
        if "│" not in line:
            continue
        parts = [p.strip() for p in line.split("│")]
        if not parts or not parts[0].isdigit() or len(parts) < 3:
            continue
        try:
            netuid = int(parts[0])
        except Exception:
            continue
        price_col = parts[2]
        num = ""
        for ch in price_col:
            if ch.isdigit() or ch == ".":
                num += ch
            elif num:
                break
        try:
            prices[netuid] = float(num)
        except Exception:
            prices[netuid] = 0.0
    return prices


def read_prices_from_btcli(btcli_path: str, network: str = "finney", timeout_sec: int = 15) -> PriceSnapshot:
    try:
        proc = subprocess.run(
            [btcli_path, "subnets", "list", "--network", network],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        prices = parse_btcli_table(proc.stdout)
        return PriceSnapshot(prices_by_netuid=prices)
    except Exception:
        # Fallback: if an environment-provided last-known-good exists, use it
        cache_path = os.environ.get("AM_LAST_PRICES_JSON")
        if cache_path and os.path.exists(cache_path):
            try:
                data = json.loads(open(cache_path, "r", encoding="utf-8").read())
                prices = {int(k): float(v) for k, v in data.items()}
                return PriceSnapshot(prices_by_netuid=prices)
            except Exception:
                pass
        # Otherwise empty
        return PriceSnapshot(prices_by_netuid={})


if TYPE_CHECKING:
    from .reports import PriceItem as _PriceItem


def read_prices_items_from_btcli(btcli_path: str, network: str = "finney", timeout_sec: int = 15) -> List["_PriceItem"]:
    """Return detailed PriceItem list if available, else fallback items with price only.

    The btcli table today does not expose block/time/pools consistently; we fill fields when
    parsable from output, else leave as None with pin_source="btcli".
    """
    try:
        from .reports import PriceItem  # type: ignore
    except Exception:
        PriceItem = None  # type: ignore
    items: List["_PriceItem"] = []
    try:
        proc = subprocess.run(
            [btcli_path, "subnets", "list", "--network", network],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        # Basic parse using existing parser
        prices = parse_btcli_table(proc.stdout)
        blk, btime = _pin_block_time()
        for uid, p in sorted(prices.items()):
            if PriceItem is not None:
                items.append(PriceItem(uid=int(uid), token=f"SN{uid}", price_in_tao=float(p), pin_source="btcli", block=blk, block_time=btime))
        return items
    except Exception:
        return items


def _pin_block_time() -> Tuple[Optional[int], Optional[str]]:
    """Try to return (block, block_time) for pinning using AM_PIN_CMD if available.

    Expects AM_PIN_CMD to output JSON with keys like {"number":..., "time":...} or {"block":..., "block_time":...}.
    Fallback to (None, None).
    """
    cmd_str = os.environ.get("AM_PIN_CMD", "").strip()
    if not cmd_str:
        return None, None
    try:
        # Security: Validate command against allowlist to prevent command injection
        allowed_commands = [
            "curl", "wget", "btcli", "cast", "eth_getBlockByNumber"
        ]
        cmd_args = cmd_str.split()
        if not cmd_args or cmd_args[0] not in allowed_commands:
            raise ValueError(f"AM_PIN_CMD command '{cmd_args[0] if cmd_args else ''}' not in allowlist")
        
        # Additional validation: no shell metacharacters
        for arg in cmd_args:
            if any(char in arg for char in ['&', '|', ';', '$', '`', '(', ')', '{', '}', '<', '>', '"', "'"]):
                raise ValueError(f"AM_PIN_CMD contains dangerous characters: {arg}")
        
        proc = subprocess.run(cmd_args, check=True, capture_output=True, text=True, timeout=10)
        data = json.loads(proc.stdout)
        # try common keys
        blk = None
        btime = None
        for k in ("number", "block", "height"):
            if k in data:
                try:
                    blk = int(data[k])
                    break
                except Exception:
                    pass
        for k in ("time", "block_time", "timestamp"):
            if k in data:
                try:
                    btime = str(data[k])
                    break
                except Exception:
                    pass
        return blk, btime
    except Exception:
        return None, None


