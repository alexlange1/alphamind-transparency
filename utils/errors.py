#!/usr/bin/env python3
"""
Custom error classes for TAO20 protocol
"""

class TAO20Error(Exception):
    """Base exception for TAO20 protocol"""
    pass

class ValidationError(TAO20Error):
    """Input validation failed"""
    pass

class ConsensusError(TAO20Error):
    """Consensus mechanism failure"""
    pass

class QuorumError(TAO20Error):
    """Insufficient quorum for operation"""
    pass

class SlippageError(TAO20Error):
    """Slippage exceeds maximum tolerance"""
    pass

class StaleDataError(TAO20Error):
    """Data is too old to be reliable"""
    pass

class InsufficientLiquidityError(TAO20Error):
    """Not enough liquidity for operation"""
    pass

class UnauthorizedError(TAO20Error):
    """Operation not authorized"""
    pass

class PausedError(TAO20Error):
    """Protocol is paused"""
    pass

class EmergencyStopError(TAO20Error):
    """Emergency stop is active"""
    pass

class IndexCompositionError(TAO20Error):
    """Index composition is invalid"""
    pass

class EligibilityError(TAO20Error):
    """Asset not eligible for inclusion"""
    pass
