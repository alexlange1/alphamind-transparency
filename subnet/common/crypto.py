#!/usr/bin/env python3
from __future__ import annotations

import hmac
import hashlib
from typing import Union


def sign_message(secret: Union[str, bytes], message: Union[str, bytes]) -> str:
    key = secret.encode() if isinstance(secret, str) else secret
    msg = message.encode() if isinstance(message, str) else message
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_signature(secret: Union[str, bytes], message: Union[str, bytes], signature: str) -> bool:
    expected = sign_message(secret, message)
    try:
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


