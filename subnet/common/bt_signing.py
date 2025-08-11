#!/usr/bin/env python3
from __future__ import annotations

import binascii
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _load_wallet(wallet_name: str, hotkey_name: str):
    try:
        import bittensor as bt  # type: ignore
        return bt.wallet(name=wallet_name, hotkey=hotkey_name)
    except ImportError:
        logging.error("Bittensor library not found. Please install it to use signing features.")
        return None
    except Exception as e:
        logging.error(f"Failed to load wallet '{wallet_name}' with hotkey '{hotkey_name}': {e}")
        return None


def sign_with_hotkey(message: bytes, wallet_name: str, hotkey_name: str) -> Optional[tuple[str, str]]:
    """Returns (signature_hex, ss58_address) or None if signing unavailable."""
    w = _load_wallet(wallet_name, hotkey_name)
    if w is None or getattr(w, "hotkey", None) is None:
        return None
    try:
        sig_bytes = w.hotkey.sign(message)
        sig_hex = binascii.hexlify(sig_bytes).decode() if isinstance(sig_bytes, bytes) else str(sig_bytes)
        return sig_hex, w.hotkey.ss58_address
    except Exception as e:
        logging.error(f"Failed to sign message with hotkey '{hotkey_name}': {e}")
        return None


def verify_with_ss58(message: bytes, signature_hex: str, ss58_address: str) -> bool:
    try:
        import bittensor as bt  # type: ignore
        from substrateinterface.utils.ss58 import is_valid_ss58_address  # type: ignore
    except ImportError:
        logging.error("Bittensor or substrate-interface library not found.")
        return False
    
    if not is_valid_ss58_address(ss58_address):
        logging.warning(f"Invalid SS58 address provided for verification: {ss58_address}")
        return False
        
    try:
        kp = bt.Keypair(ss58_address=ss58_address)
        sig = binascii.unhexlify(signature_hex)
        return kp.verify(message, sig)
    except binascii.Error:
        logging.error("Invalid hex signature provided for verification.")
        return False
    except Exception as e:
        logging.error(f"Failed to verify signature for address '{ss58_address}': {e}")
        return False


