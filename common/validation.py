#!/usr/bin/env python3
"""
Input validation utilities for TAO20 protocol
"""
from typing import Dict, List, Any, Optional
import re
from decimal import Decimal, InvalidOperation


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def validate_positive_amount(amount: float, name: str = "amount") -> float:
    """Validate that amount is positive and reasonable"""
    if not isinstance(amount, (int, float)):
        raise ValidationError(f"{name} must be a number")
    
    if amount <= 0:
        raise ValidationError(f"{name} must be positive")
    
    if amount > 1e18:  # Reasonable upper bound
        raise ValidationError(f"{name} too large")
    
    return float(amount)


def validate_netuid(netuid: int) -> int:
    """Validate subnet ID is within reasonable bounds"""
    if not isinstance(netuid, int):
        raise ValidationError("netuid must be an integer")
    
    if netuid < 0 or netuid > 1000:  # Reasonable bounds for Bittensor
        raise ValidationError(f"netuid {netuid} out of bounds")
    
    return netuid


def validate_weights(weights: Dict[int, float]) -> Dict[int, float]:
    """Validate weight dictionary structure and values"""
    if not isinstance(weights, dict):
        raise ValidationError("weights must be a dictionary")
    
    if len(weights) == 0:
        raise ValidationError("weights cannot be empty")
    
    if len(weights) > 20:
        raise ValidationError("too many weights (max 20)")
    
    validated = {}
    total_weight = 0.0
    
    for netuid, weight in weights.items():
        validated_netuid = validate_netuid(netuid)
        
        if not isinstance(weight, (int, float)):
            raise ValidationError(f"weight for netuid {netuid} must be a number")
        
        if weight < 0 or weight > 1:
            raise ValidationError(f"weight for netuid {netuid} must be between 0 and 1")
        
        validated[validated_netuid] = float(weight)
        total_weight += float(weight)
    
    # Allow small floating point errors
    if abs(total_weight - 1.0) > 1e-6:
        raise ValidationError(f"weights must sum to 1.0, got {total_weight}")
    
    return validated


def validate_prices(prices: Dict[int, float]) -> Dict[int, float]:
    """Validate price dictionary structure and values"""
    if not isinstance(prices, dict):
        raise ValidationError("prices must be a dictionary")
    
    if len(prices) == 0:
        raise ValidationError("prices cannot be empty")
    
    validated = {}
    for netuid, price in prices.items():
        validated_netuid = validate_netuid(netuid)
        validated_price = validate_positive_amount(price, f"price for netuid {netuid}")
        validated[validated_netuid] = validated_price
    
    return validated


def validate_basket(basket: Dict[int, float]) -> Dict[int, float]:
    """Validate in-kind basket quantities"""
    if not isinstance(basket, dict):
        raise ValidationError("basket must be a dictionary")
    
    if len(basket) == 0:
        raise ValidationError("basket cannot be empty")
    
    if len(basket) > 20:
        raise ValidationError("basket too large (max 20 assets)")
    
    validated = {}
    for netuid, quantity in basket.items():
        validated_netuid = validate_netuid(netuid)
        validated_quantity = validate_positive_amount(quantity, f"quantity for netuid {netuid}")
        validated[validated_netuid] = validated_quantity
    
    return validated


def validate_ss58_address(address: str) -> str:
    """Validate Substrate SS58 address format"""
    if not isinstance(address, str):
        raise ValidationError("address must be a string")
    
    # Basic SS58 format check (simplified)
    if len(address) < 47 or len(address) > 48:
        raise ValidationError("invalid SS58 address length")
    
    # Check for valid base58 characters
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if not all(c in valid_chars for c in address):
        raise ValidationError("invalid SS58 address characters")
    
    return address


def validate_signature(signature: str) -> str:
    """Validate cryptographic signature format"""
    if not isinstance(signature, str):
        raise ValidationError("signature must be a string")
    
    # Basic hex string validation
    if not re.match(r'^[0-9a-fA-F]+$', signature):
        raise ValidationError("signature must be hex string")
    
    if len(signature) < 128 or len(signature) > 132:  # Typical signature lengths
        raise ValidationError("invalid signature length")
    
    return signature


def validate_timestamp(timestamp: str) -> str:
    """Validate ISO 8601 timestamp format"""
    if not isinstance(timestamp, str):
        raise ValidationError("timestamp must be a string")
    
    # Basic ISO 8601 format check
    pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'
    if not re.match(pattern, timestamp):
        raise ValidationError("timestamp must be ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)")
    
    return timestamp


def validate_percentage_bps(bps: int, name: str = "basis points") -> int:
    """Validate basis points (0-10000)"""
    if not isinstance(bps, int):
        raise ValidationError(f"{name} must be an integer")
    
    if bps < 0 or bps > 10000:
        raise ValidationError(f"{name} must be between 0 and 10000")
    
    return bps


def sanitize_file_path(path: str) -> str:
    """Sanitize file path to prevent directory traversal"""
    if not isinstance(path, str):
        raise ValidationError("path must be a string")
    
    # Remove potentially dangerous characters
    dangerous_patterns = ['..', '~', '$', '`', '|', ';', '&']
    for pattern in dangerous_patterns:
        if pattern in path:
            raise ValidationError(f"path contains dangerous pattern: {pattern}")
    
    return path
