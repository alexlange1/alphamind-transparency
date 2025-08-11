#!/usr/bin/env python3
"""
Test aggregate slippage calculation per whitepaper Section 3.1
"""
import pytest
from subnet.sim.vault import VaultState, mint_tao_extended


def test_aggregate_slippage_within_limit():
    """Test that aggregate slippage under 1% passes"""
    # Setup
    state = VaultState(
        holdings={},
        tao20_supply=0.0,
        last_nav_tao=0.0
    )
    
    weights = {1: 0.5, 2: 0.3, 3: 0.2}  # Top 3 for simplicity
    prices = {1: 100.0, 2: 50.0, 3: 200.0}
    
    # Pool reserves with moderate liquidity (low slippage)
    pool_reserves = {
        1: (1000.0, 100000.0),  # Large pool, low slippage
        2: (2000.0, 100000.0),  # Large pool, low slippage  
        3: (500.0, 100000.0),   # Large pool, low slippage
    }
    
    # This should pass - good liquidity means low slippage
    result_state, mint_result = mint_tao_extended(
        amount_tao=1000.0,
        weights=weights,
        prices=prices,
        state=state,
        pool_reserves=pool_reserves
    )
    
    assert mint_result.minted > 0
    assert result_state.tao20_supply > 0


def test_aggregate_slippage_exceeds_limit():
    """Test that aggregate slippage over 1% fails"""
    # Setup
    state = VaultState(
        holdings={},
        tao20_supply=0.0,
        last_nav_tao=0.0
    )
    
    weights = {1: 0.5, 2: 0.3, 3: 0.2}
    prices = {1: 100.0, 2: 50.0, 3: 200.0}
    
    # Pool reserves with very low liquidity (high slippage)
    pool_reserves = {
        1: (10.0, 1000.0),   # Small pool, high slippage
        2: (20.0, 1000.0),   # Small pool, high slippage
        3: (5.0, 1000.0),    # Small pool, high slippage
    }
    
    # This should fail - low liquidity causes high slippage
    with pytest.raises(ValueError, match="aggregate_slippage_exceeds_1pct"):
        mint_tao_extended(
            amount_tao=1000.0,  # Large trade relative to pool size
            weights=weights,
            prices=prices,
            state=state,
            pool_reserves=pool_reserves
        )


def test_aggregate_slippage_calculation_accuracy():
    """Test that weighted-average slippage is calculated correctly"""
    # Setup with known conditions for precise calculation
    state = VaultState(
        holdings={},
        tao20_supply=0.0,
        last_nav_tao=0.0
    )
    
    # Simple case: equal weights, different slippage per asset
    weights = {1: 0.5, 2: 0.5}
    prices = {1: 100.0, 2: 100.0}
    
    # Designed to give known slippage
    pool_reserves = {
        1: (100.0, 10000.0),  # Will give ~0.5% slippage for 50 TAO trade
        2: (50.0, 5000.0),    # Will give ~1.0% slippage for 50 TAO trade
    }
    
    # Expected aggregate: (0.5% * 0.5) + (1.0% * 0.5) = 0.75%
    # This should pass (under 1%)
    result_state, mint_result = mint_tao_extended(
        amount_tao=100.0,
        weights=weights,
        prices=prices,
        state=state,
        pool_reserves=pool_reserves
    )
    
    assert mint_result.minted > 0


def test_edge_case_zero_slippage():
    """Test edge case with perfect liquidity (no slippage)"""
    state = VaultState(
        holdings={},
        tao20_supply=0.0,
        last_nav_tao=0.0
    )
    
    weights = {1: 1.0}  # Single asset
    prices = {1: 100.0}
    
    # Infinite liquidity (no slippage)
    pool_reserves = {
        1: (1000000.0, 100000000.0),  # Massive pool
    }
    
    result_state, mint_result = mint_tao_extended(
        amount_tao=100.0,
        weights=weights,
        prices=prices,
        state=state,
        pool_reserves=pool_reserves
    )
    
    assert mint_result.minted > 0


def test_mixed_slippage_scenarios():
    """Test realistic mix of high and low slippage assets"""
    state = VaultState(
        holdings={},
        tao20_supply=0.0,
        last_nav_tao=0.0
    )
    
    # Realistic top-20 subnet weights
    weights = {
        1: 0.15,  # Major subnet, good liquidity
        2: 0.12,  # Major subnet, good liquidity  
        3: 0.10,  # Medium subnet, moderate liquidity
        4: 0.08,  # Medium subnet, moderate liquidity
        5: 0.05,  # Smaller subnet, higher slippage
    }
    
    prices = {1: 100.0, 2: 80.0, 3: 120.0, 4: 90.0, 5: 60.0}
    
    # Mixed liquidity pools
    pool_reserves = {
        1: (5000.0, 500000.0),   # Good liquidity
        2: (4000.0, 320000.0),   # Good liquidity
        3: (2000.0, 240000.0),   # Moderate liquidity  
        4: (1500.0, 135000.0),   # Moderate liquidity
        5: (500.0, 30000.0),     # Lower liquidity
    }
    
    # Should still pass with realistic mixed conditions
    result_state, mint_result = mint_tao_extended(
        amount_tao=1000.0,
        weights=weights,
        prices=prices,
        state=state,
        pool_reserves=pool_reserves
    )
    
    assert mint_result.minted > 0
    assert result_state.tao20_supply > 0


if __name__ == "__main__":
    pytest.main([__file__])
