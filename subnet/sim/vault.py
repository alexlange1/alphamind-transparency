#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


@dataclass
class VaultState:
    # Quantity of each subnet token held by the vault
    holdings: Dict[int, float]
    # Total TAO20 supply outstanding
    tao20_supply: float
    # Last known NAV per token (TAO terms)
    last_nav_tao: float
    # Fee accounting (TAO terms for tx and mgmt); last management fee accrual timestamp (ISO8601 Z)
    fees_tx_tao: float = 0.0
    fees_mgmt_tao: float = 0.0
    last_mgmt_ts: str = ""

    def to_json(self) -> str:
        data = {
            "holdings": {str(k): v for k, v in self.holdings.items()},
            "tao20_supply": self.tao20_supply,
            "last_nav_tao": self.last_nav_tao,
            "fees_tx_tao": self.fees_tx_tao,
            "fees_mgmt_tao": self.fees_mgmt_tao,
            "last_mgmt_ts": self.last_mgmt_ts,
        }
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "VaultState":
        raw = json.loads(text)
        return VaultState(
            holdings={int(k): float(v) for k, v in (raw.get("holdings") or {}).items()},
            tao20_supply=float(raw.get("tao20_supply", 0.0)),
            last_nav_tao=float(raw.get("last_nav_tao", 0.0)),
            fees_tx_tao=float(raw.get("fees_tx_tao", 0.0)),
            fees_mgmt_tao=float(raw.get("fees_mgmt_tao", 0.0)),
            last_mgmt_ts=str(raw.get("last_mgmt_ts", "")),
        )


def load_vault(path: Path) -> Optional[VaultState]:
    try:
        return VaultState.from_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_vault(path: Path, state: VaultState) -> None:
    path.write_text(state.to_json(), encoding="utf-8")


def initialize_vault(weights: Dict[int, float], prices: Dict[int, float], initial_nav: float = 100.0, initial_supply: float = 1000.0) -> VaultState:
    # Distribute value by weights so that total portfolio value equals supply * initial_nav
    target_value = initial_supply * initial_nav
    holdings: Dict[int, float] = {}
    for netuid, w in weights.items():
        price = float(prices.get(netuid, 0.0)) or 1e-9
        value_alloc = target_value * float(w)
        qty = value_alloc / price
        holdings[netuid] = qty
    return VaultState(holdings=holdings, tao20_supply=initial_supply, last_nav_tao=initial_nav)


def compute_nav(prices: Dict[int, float], state: VaultState) -> float:
    total_value = 0.0
    for netuid, qty in state.holdings.items():
        total_value += float(qty) * float(prices.get(netuid, 0.0))
    if state.tao20_supply <= 0:
        return 0.0
    return total_value / state.tao20_supply


def apply_mint_with_tao(amount_tao: float, weights: Dict[int, float], prices: Dict[int, float], state: VaultState, fee_bps: int = 20) -> VaultState:
    """Simplified mint via TAO: allocate TAO across basket by weights, convert to qty, increase supply at NAV.
    fee_bps: 0.2% default (20 bps)."""
    fee = float(amount_tao) * max(0.0, fee_bps) / 10000.0
    net_tao = float(amount_tao) - fee
    # Add holdings by value per weights
    for netuid, w in weights.items():
        price = float(prices.get(netuid, 0.0)) or 1e-9
        value_alloc = net_tao * float(w)
        qty = value_alloc / price
        state.holdings[netuid] = state.holdings.get(netuid, 0.0) + qty
    # Mint supply at current NAV after adding? Use pre-trade NAV for issuance fairness
    pre_nav = compute_nav(prices, state)
    if pre_nav <= 0:
        minted = 0.0
    else:
        minted = net_tao / pre_nav
    state.tao20_supply += minted
    state.last_nav_tao = compute_nav(prices, state)
    state.fees_tx_tao += fee
    return state


def apply_redeem_in_kind(amount_tao20: float, prices: Dict[int, float], state: VaultState) -> VaultState:
    """Redeem in kind: burn supply and reduce holdings pro-rata. No TAO transfer simulated."""
    if amount_tao20 <= 0 or state.tao20_supply <= 0:
        return state
    ratio = min(1.0, amount_tao20 / state.tao20_supply)
    for netuid, qty in list(state.holdings.items()):
        state.holdings[netuid] = qty * (1.0 - ratio)
    state.tao20_supply -= amount_tao20
    if state.tao20_supply < 0:
        state.tao20_supply = 0.0
    state.last_nav_tao = compute_nav(prices, state)
    return state



def apply_mint_in_kind(basket: Dict[int, float], prices: Dict[int, float], state: VaultState, fee_bps: int = 20) -> VaultState:
    """Mint in kind: depositor provides basket quantities. We add holdings and mint supply
    equivalent to net contributed value at pre-trade NAV. Fee reduces minted supply (NAV accretes fee).
    """
    if not basket:
        return state
    # Compute pre-trade NAV
    pre_nav = compute_nav(prices, state)
    # Compute contribution value
    gross_value = 0.0
    for netuid, qty in basket.items():
        price = float(prices.get(int(netuid), 0.0))
        gross_value += float(qty) * price
    fee = gross_value * max(0.0, fee_bps) / 10000.0
    net_value = gross_value - fee
    # Add holdings
    for netuid, qty in basket.items():
        nid = int(netuid)
        state.holdings[nid] = state.holdings.get(nid, 0.0) + float(qty)
    # Mint supply
    minted = 0.0
    if pre_nav > 0 and net_value > 0:
        minted = net_value / pre_nav
    state.tao20_supply += minted
    state.last_nav_tao = compute_nav(prices, state)
    state.fees_tx_tao += fee
    return state


def apply_management_fee(prices: Dict[int, float], state: VaultState, now_iso_ts: str | None = None, min_interval_days: int = 1) -> VaultState:
    """Accrue management fee by minting supply to manager based on 1%/yr.
    Applies only if at least min_interval_days since last_mgmt_ts.
    Records fee value in TAO at pre-accrual NAV.
    """
    if state.tao20_supply <= 0:
        # Initialize last_mgmt_ts if missing
        if not state.last_mgmt_ts:
            state.last_mgmt_ts = datetime.strftime(datetime.now(timezone.utc), "%Y-%m-%dT%H:%M:%SZ")
        return state
    now = datetime.now(timezone.utc) if not now_iso_ts else datetime.strptime(now_iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if state.last_mgmt_ts:
        try:
            last = datetime.strptime(state.last_mgmt_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            last = datetime.fromtimestamp(0, tz=timezone.utc)
    else:
        last = now
    days = int((now - last).total_seconds() // (24 * 3600))
    if days < max(1, int(min_interval_days)):
        return state
    r_daily = (1.0 + 0.01) ** (1.0 / 365.0) - 1.0
    pre_nav = compute_nav(prices, state)
    s0 = state.tao20_supply
    s1 = s0 * ((1.0 + r_daily) ** days)
    delta_s = max(0.0, s1 - s0)
    state.tao20_supply = s1
    state.fees_mgmt_tao += delta_s * pre_nav
    state.last_nav_tao = compute_nav(prices, state)
    state.last_mgmt_ts = datetime.strftime(now, "%Y-%m-%dT%H:%M:%SZ")
    return state


