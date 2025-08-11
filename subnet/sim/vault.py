#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import json
import os
import fcntl


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
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = f.read()
            fcntl.flock(f, fcntl.LOCK_UN)
        return VaultState.from_json(data)
    except (IOError, json.JSONDecodeError):
        return None


def save_vault(path: Path, state: VaultState) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(state.to_json())
            fcntl.flock(f, fcntl.LOCK_UN)
    except IOError:
        pass  # Or log an error


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
    # Mint supply using proper bootstrap logic
    if state.tao20_supply <= 0:
        # Bootstrap case: mint 1:1 with net TAO value
        minted = net_tao
    else:
        # Standard case: mint based on NAV
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


def reinvest_fees_to_alpha(prices: Dict[int, float], base: Path, alpha_price_in_tao: float = 1.0) -> FeesLedger:
    """Convert accrued TAO and token value to Alpha. Zeroes accruals."""
    if alpha_price_in_tao <= 0:
        return load_fees_ledger(base)
        
    ledger = load_fees_ledger(base)
    # Compute total TAO value of token accruals
    token_value = 0.0
    for uid, qty in (ledger.accrued_tokens or {}).items():
        token_value += float(qty) * float(prices.get(int(uid), 0.0))
    total_value = float(ledger.accrued_tao) + token_value
    if total_value > 0:
        ledger.alpha_qty += total_value / alpha_price_in_tao
    ledger.accrued_tao = 0.0
    ledger.accrued_tokens = {}
    save_fees_ledger(base, ledger)
    return ledger


# ===================== PR3 helpers =====================


@dataclass(frozen=True)
class Residual:
    uid: int
    qty: float


@dataclass(frozen=True)
class MintResult:
    minted: float
    nav_per_tao20: float
    residuals: List[Residual]
    pricing_mode: str = "CONSENSUS"


@dataclass(frozen=True)
class RedeemResult:
    basket_out: List[Residual]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _weights_from_bps_map(bps: Dict[int, int]) -> Dict[int, float]:
    denom = float(sum(int(v) for v in bps.values()) or 1)
    return {int(k): int(v) / denom for k, v in bps.items()}


def _bps_from_weights(weights: Dict[int, float], total_bps: int = 10000) -> Dict[int, int]:
    # Normalize weights to sum to 1.0
    denom = sum(float(v) for v in weights.values()) or 1.0
    items = sorted(((int(k), float(v) / denom) for k, v in weights.items()), key=lambda kv: (-kv[1], kv[0]))
    floors: Dict[int, int] = {}
    fracs: List[Tuple[float, int]] = []
    s = 0
    for uid, w in items:
        raw = w * total_bps
        fl = int(raw)
        floors[uid] = fl
        fracs.append((raw - fl, uid))
        s += fl
    rem = max(0, total_bps - s)
    fracs.sort(key=lambda x: (-x[0], x[1]))
    for i in range(rem):
        if i < len(fracs):
            floors[fracs[i][1]] += 1
    return floors


# ===================== Fees ledger =====================


@dataclass
class FeesLedger:
    accrued_tao: float = 0.0
    accrued_tokens: Dict[int, float] = None  # uid -> qty
    last_mgmt_fee_ts: str = ""
    alpha_qty: float = 0.0

    def to_json(self) -> str:
        return json.dumps({
            "accrued_tao": float(self.accrued_tao),
            "accrued_tokens": {str(int(k)): float(v) for k, v in (self.accrued_tokens or {}).items()},
            "last_mgmt_fee_ts": self.last_mgmt_fee_ts,
            "alpha_qty": float(self.alpha_qty),
        }, separators=(",", ":"))

    @staticmethod
    def from_json(text: str) -> "FeesLedger":
        raw = json.loads(text)
        return FeesLedger(
            accrued_tao=float(raw.get("accrued_tao", 0.0)),
            accrued_tokens={int(k): float(v) for k, v in (raw.get("accrued_tokens") or {}).items()},
            last_mgmt_fee_ts=str(raw.get("last_mgmt_fee_ts", "")),
            alpha_qty=float(raw.get("alpha_qty", 0.0)),
        )


def _fees_path(base: Path) -> Path:
    p = base / "fees_state.json"
    return p


def load_fees_ledger(base: Path) -> FeesLedger:
    try:
        return FeesLedger.from_json(_fees_path(base).read_text(encoding="utf-8"))
    except Exception:
        return FeesLedger(accrued_tao=0.0, accrued_tokens={}, last_mgmt_fee_ts="", alpha_qty=0.0)


def save_fees_ledger(base: Path, ledger: FeesLedger) -> None:
    _fees_path(base).write_text(ledger.to_json(), encoding="utf-8")


def mint_tao_extended(amount_tao: float, weights: Dict[int, float], prices: Dict[int, float], state: VaultState, max_slippage_bps: Optional[int] = None, fee_bps: Optional[int] = None, simulated_slippage_bps: Optional[int] = None, pool_reserves: Optional[Dict[int, Tuple[float, float]]] = None, fees_base: Optional[Path] = None) -> Tuple[VaultState, MintResult]:
    """Mint via TAO with slippage guard and residual reporting.

    Slippage is simulated via optional parameter or env AM_SIM_SLIPPAGE_BPS for testing.
    """
    if fee_bps is None:
        fee_bps = _env_int("AM_MINT_FEE_BPS", 20)
    if max_slippage_bps is None:
        max_slippage_bps = _env_int("AM_MAX_SLIPPAGE_BPS", 100)
    if simulated_slippage_bps is None:
        try:
            simulated_slippage_bps = int(os.environ.get("AM_SIM_SLIPPAGE_BPS", "0"))
        except Exception:
            simulated_slippage_bps = 0
    # Aggregate slippage calculation for whitepaper compliance (Section 3.1)
    if pool_reserves and amount_tao > 0:
        # Compute exact weighted-average slippage across all 20 trades
        total_weight = sum(weights.values()) or 1.0
        total_weighted_slippage = 0.0
        total_weight_sum = 0.0
        
        for uid, w in weights.items():
            alloc = amount_tao * (float(w) / total_weight)
            price = float(prices.get(int(uid), 0.0)) or 0.0
            reserves = pool_reserves.get(int(uid)) if pool_reserves else None
            if price <= 0 or not reserves:
                continue
            rtok, rtao = reserves
            
            # Calculate expected quantity at current price
            expected_qty = alloc / price
            
            # Constant product x*y=k slippage calculation
            # New TAO reserve = rtao + alloc
            # New token reserve = (rtok * rtao) / (rtao + alloc)  
            # Actual qty received = rtok - new_token_reserve
            new_rtao = rtao + alloc
            new_rtok = (rtok * rtao) / new_rtao
            actual_qty = rtok - new_rtok
            
            # Calculate individual slippage in basis points
            individual_slippage_bps = 0.0
            if expected_qty > 0 and actual_qty < expected_qty:
                individual_slippage_bps = ((expected_qty - actual_qty) / expected_qty) * 10000.0
            
            # Add to weighted average (weight by allocation size)
            total_weighted_slippage += individual_slippage_bps * w
            total_weight_sum += w
            
        # Calculate aggregate weighted-average slippage
        avg_slippage_bps = total_weighted_slippage / total_weight_sum if total_weight_sum > 0 else 0.0
        
        # Enforce 1% aggregate slippage limit per whitepaper Section 3.1
        if avg_slippage_bps > 100.0:  # 1% = 100 bps
            raise ValueError(f"aggregate_slippage_exceeds_1pct: {avg_slippage_bps:.2f}bps")
    elif simulated_slippage_bps and simulated_slippage_bps > max_slippage_bps:
        raise ValueError("slippage_exceeds_max")
    # Apply fee and reuse existing logic (no on-chain swap simulation here)
    s0 = VaultState.from_json(state.to_json())
    # Accrue fee to fees ledger (TAO)
    try:
        if fees_base is not None:
            ledger = load_fees_ledger(fees_base)
            fee_amt = float(amount_tao) * max(0.0, fee_bps) / 10000.0
            ledger.accrued_tao += fee_amt
            save_fees_ledger(fees_base, ledger)
    except Exception:
        pass
    s1 = apply_mint_with_tao(amount_tao, weights, prices, state, fee_bps=fee_bps)
    nav = compute_nav(prices, s1)
    minted = s1.tao20_supply - s0.tao20_supply
    # Compute residuals relative to target allocation after CPMM-like buys
    try:
        eps_bps = _env_int("AM_RESIDUAL_EPSILON_BPS", 5)
    except Exception:
        eps_bps = 5
    epsilon = max(0.0, float(eps_bps)) / 10000.0
    # Post-fee TAO allocated by weights
    fee_amt = float(amount_tao) * max(0.0, fee_bps) / 10000.0
    post_fee_tao = float(amount_tao) - fee_amt
    residuals: List[Residual] = []
    # Simulate acquired quantities using integer bps allocation to mimic rounding + on-chain execution
    bps_map = _bps_from_weights(weights)
    for uid, w in weights.items():
        price = float(prices.get(int(uid), 0.0)) or 0.0
        if price <= 0 or w <= 0:
            continue
        target_qty = (post_fee_tao * float(w)) / price
        # Integer bps allocation TAO share
        alloc_tao = post_fee_tao * (float(bps_map.get(int(uid), 0)) / 10000.0)
        acquired_qty = alloc_tao / price if price > 0 else 0.0
        res = max(0.0, acquired_qty - target_qty * (1.0 + epsilon))
        if res > 0:
            residuals.append(Residual(uid=int(uid), qty=res))
    return s1, MintResult(minted=minted, nav_per_tao20=nav, residuals=residuals, pricing_mode="CONSENSUS")


def mint_in_kind_extended(basket: Dict[int, float], weights: Dict[int, float], prices: Dict[int, float], state: VaultState, max_deviation_bps: Optional[int] = None, fee_bps: Optional[int] = None, fees_base: Optional[Path] = None) -> Tuple[VaultState, MintResult]:
    if fee_bps is None:
        fee_bps = _env_int("AM_MINT_FEE_BPS", 20)
    if max_deviation_bps is None:
        max_deviation_bps = _env_int("AM_INKIND_DEV_BPS", 5)
    # Proportion check by value
    total_val = 0.0
    val_by_uid: Dict[int, float] = {}
    for uid, qty in basket.items():
        price = float(prices.get(int(uid), 0.0))
        v = float(qty) * price
        val_by_uid[int(uid)] = v
        total_val += v
    if total_val <= 0:
        raise ValueError("empty_basket")
    for uid, v in val_by_uid.items():
        share = v / total_val
        tw = float(weights.get(int(uid), 0.0))
        dev = abs(share - tw)
        if tw > 0:
            dev_bps = int(dev / tw * 10000)
            if dev_bps > max_deviation_bps:
                raise ValueError("basket_deviation_exceeds_limit")
    s0 = VaultState.from_json(state.to_json())
    # Accrue fee value (TAO) from in-kind mint
    try:
        if fees_base is not None:
            ledger = load_fees_ledger(fees_base)
            # compute gross value
            gross = 0.0
            for uid, qty in basket.items():
                gross += float(qty) * float(prices.get(int(uid), 0.0))
            fee_amt = gross * max(0.0, fee_bps) / 10000.0
            ledger.accrued_tao += fee_amt
            save_fees_ledger(fees_base, ledger)
    except Exception:
        pass
    s1 = apply_mint_in_kind(basket, prices, state, fee_bps=fee_bps)
    nav = compute_nav(prices, s1)
    minted = s1.tao20_supply - s0.tao20_supply
    return s1, MintResult(minted=minted, nav_per_tao20=nav, residuals=[], pricing_mode="CONSENSUS")


def redeem_in_kind_extended(amount_tao20: float, prices: Dict[int, float], state: VaultState, fee_bps: Optional[int] = None, fees_base: Optional[Path] = None) -> Tuple[VaultState, RedeemResult]:
    if fee_bps is None:
        fee_bps = _env_int("AM_REDEEM_FEE_BPS", 20)
    if amount_tao20 <= 0 or state.tao20_supply <= 0:
        return state, RedeemResult(basket_out=[])
    # Pro-rata baseline
    ratio = min(1.0, amount_tao20 / state.tao20_supply)
    basket_out: List[Residual] = []
    for uid, qty in list(state.holdings.items()):
        out_qty = qty * ratio
        basket_out.append(Residual(uid=int(uid), qty=out_qty))
    # Apply in-kind redeem fee: reduce basket_out proportionally
    fee_mult = max(0.0, 1.0 - (fee_bps / 10000.0))
    basket_out = [Residual(uid=b.uid, qty=b.qty * fee_mult) for b in basket_out]
    # Accrue token fees
    try:
        if fees_base is not None:
            ledger = load_fees_ledger(fees_base)
            for b in basket_out:
                # fee in tokens = original out minus net out
                orig = next((x.qty for x in basket_out if x.uid == b.uid), b.qty)
                fee_qty = orig * (1.0 - fee_mult)
                if fee_qty > 0:
                    ledger.accrued_tokens[b.uid] = (ledger.accrued_tokens or {}).get(b.uid, 0.0) + fee_qty
            save_fees_ledger(fees_base, ledger)
    except Exception:
        pass
    # Burn and reduce holdings accordingly
    for b in basket_out:
        state.holdings[b.uid] = max(0.0, state.holdings.get(b.uid, 0.0) - (b.qty))
    state.tao20_supply = max(0.0, state.tao20_supply - amount_tao20)
    state.last_nav_tao = compute_nav(prices, state)
    return state, RedeemResult(basket_out=basket_out)


