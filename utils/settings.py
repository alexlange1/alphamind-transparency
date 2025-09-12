#!/usr/bin/env python3
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """Centralized environment-driven settings (non-breaking scaffold).

    This module does not alter existing defaults; callers must opt-in.
    """

    # FIXED: Use relative paths instead of hardcoded user paths
    out_dir: str = os.environ.get("AM_OUT_DIR", os.path.join(os.path.dirname(__file__), "..", "out"))
    in_dir: str = os.environ.get("AM_IN_DIR", os.path.join(os.path.dirname(__file__), "..", "out"))
    btcli_path: str = os.environ.get("AM_BTCLI", "btcli")  # Assume btcli is in PATH

    miner_secret: str = os.environ.get("AM_MINER_SECRET", "")
    wallet_name: str = os.environ.get("AM_WALLET", "")
    hotkey_name: str = os.environ.get("AM_HOTKEY", "")

    emissions_quorum: float = float(os.environ.get("AM_EMISSIONS_QUORUM", 0.7))
    price_quorum: float = float(os.environ.get("AM_PRICE_QUORUM", 0.7))
    emissions_band_pct: float = float(os.environ.get("AM_EMISSIONS_BAND_PCT", 0.5))
    price_band_pct: float = float(os.environ.get("AM_PRICE_BAND_PCT", 0.2))
    price_stale_sec: int = int(os.environ.get("AM_PRICE_STALE_SEC", 120))

    # Centralized policy constants (single source of truth)
    max_trade_slippage_pct: float = float(os.environ.get("AM_MAX_TRADE_SLIPPAGE_PCT", 0.005))
    entry_margin_pct: float = float(os.environ.get("AM_ENTRY_MARGIN_PCT", 0.005))
    sustain_days: int = int(os.environ.get("AM_SUSTAIN_DAYS", 3))
    te_threshold_bps: int = int(os.environ.get("AM_TE_THRESHOLD_BPS", 200))
    twap_window_min: int = int(os.environ.get("AM_TWAP_WINDOW_MIN", 30))
    deviation_cap_bps: int = int(os.environ.get("AM_DEVIATION_CAP_BPS", 100))  # 1%
    min_liquidity_threshold: float = float(os.environ.get("AM_MIN_LIQ_THRESHOLD", 1.0))
    quorum_stake_pct: float = float(os.environ.get("AM_QUORUM_STAKE_PCT", 0.7))

    # TWAP warm-up parameters
    min_twap_obs: int = int(os.environ.get("AM_MIN_TWAP_OBS", 5))
    min_twap_coverage_sec: int = int(os.environ.get("AM_MIN_TWAP_COVERAGE_SEC", 600))

    api_token: str = os.environ.get("AM_API_TOKEN", "")
    cors_origins: str = os.environ.get("AM_CORS_ORIGINS", "*")

    # Snapshot settings
    network: str = os.environ.get("AM_NETWORK", "finney")
    snapshot_grace_sec: int = int(os.environ.get('AM_SNAPSHOT_GRACE_SEC', '120'))
    btcli_timeout_sec: int = int(os.environ.get("AM_BTCLI_TIMEOUT_SEC", "30"))
    json_missing_tolerance: float = float(os.environ.get("AM_JSON_MISSING_TOLERANCE", "0.0"))
    strict_registry: bool = os.environ.get('AM_STRICT_REGISTRY', '1') == '1'
    allow_table_mode: bool = os.environ.get("ALLOW_TABLE_MODE", "0") == "1"
    idempotent_append: bool = os.environ.get("AM_IDEMPOTENT_APPEND", "1") == "1"
    max_tsv_size_mb: int = int(os.environ.get('AM_MAX_TSV_SIZE_MB', '100'))
    min_emission_threshold: float = float(os.environ.get('AM_MIN_EMISSION_THRESHOLD', '1e-9'))
    netuid_registry_file: Optional[str] = os.environ.get('AM_NETUID_REGISTRY')
    known_netuids: str = os.environ.get('AM_KNOWN_NETUIDS', '')
    include_low_trust_14d: bool = os.environ.get('AM_INCLUDE_LOW_TRUST_14D', '0') == '1'
    include_low_trust_elig: bool = os.environ.get('AM_INCLUDE_LOW_TRUST_ELIG', '0') == '1'


def get_settings() -> Settings:
    return Settings()


