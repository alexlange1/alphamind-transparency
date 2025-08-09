#!/usr/bin/env python3
from __future__ import annotations

import binascii
from typing import Optional


def _load_wallet(wallet_name: str, hotkey_name: str):
    try:
        import bittensor as bt  # type: ignore
    except Exception:
        return None
    try:
        w = bt.wallet(name=wallet_name, hotkey=hotkey_name)
        return w
    except Exception:
        return None


def sign_with_hotkey(message: bytes, wallet_name: str, hotkey_name: str) -> Optional[tuple[str, str]]:
    """Returns (signature_hex, ss58_address) or None if signing unavailable."""
    w = _load_wallet(wallet_name, hotkey_name)
    if w is None or getattr(w, "hotkey", None) is None:
        return None
    try:
        sig_bytes = w.hotkey.sign(message)
        if isinstance(sig_bytes, bytes):
            sig_hex = binascii.hexlify(sig_bytes).decode()
        else:
            # some versions return hex already
            sig_hex = str(sig_bytes)
        return sig_hex, w.hotkey.ss58_address
    except Exception:
        return None


def verify_with_ss58(message: bytes, signature_hex: str, ss58_address: str) -> bool:
    try:
        import bittensor as bt  # type: ignore
        from substrateinterface.utils.ss58 import is_valid_ss58_address  # type: ignore
    except Exception:
        return False
    try:
        if not is_valid_ss58_address(ss58_address):
            return False
        kp = bt.Keypair(ss58_address=ss58_address)
        sig = binascii.unhexlify(signature_hex)
        return bool(kp.verify(message, sig))
    except Exception:
        return False


