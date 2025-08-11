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

    out_dir: str = os.environ.get("AM_OUT_DIR", "/Users/alexanderlange/alphamind/subnet/out")
    in_dir: str = os.environ.get("AM_IN_DIR", "/Users/alexanderlange/alphamind/subnet/out")
    btcli_path: str = os.environ.get("AM_BTCLI", "/Users/alexanderlange/.venvs/alphamind/bin/btcli")

    miner_secret: str = os.environ.get("AM_MINER_SECRET", "")
    wallet_name: str = os.environ.get("AM_WALLET", "")
    hotkey_name: str = os.environ.get("AM_HOTKEY", "")

    emissions_quorum: float = float(os.environ.get("AM_EMISSIONS_QUORUM", 0.33))
    price_quorum: float = float(os.environ.get("AM_PRICE_QUORUM", 0.33))
    emissions_band_pct: float = float(os.environ.get("AM_EMISSIONS_BAND_PCT", 0.5))
    price_band_pct: float = float(os.environ.get("AM_PRICE_BAND_PCT", 0.2))
    price_stale_sec: int = int(os.environ.get("AM_PRICE_STALE_SEC", 120))

    api_token: str = os.environ.get("AM_API_TOKEN", "")
    cors_origins: str = os.environ.get("AM_CORS_ORIGINS", "*")


def get_settings() -> Settings:
    return Settings()


