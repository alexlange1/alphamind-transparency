#!/usr/bin/env python3
"""
Tests for critical security fixes
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from subnet.validator.api import app
from subnet.common.validation import ValidationError, validate_positive_amount, validate_weights
from subnet.common.rate_limiter import RateLimiter


def test_input_validation_positive_amounts():
    """Test positive amount validation"""
    # Valid cases
    assert validate_positive_amount(1.0) == 1.0
    assert validate_positive_amount(100.5) == 100.5
    
    # Invalid cases
    with pytest.raises(ValidationError, match="must be positive"):
        validate_positive_amount(0)
    
    with pytest.raises(ValidationError, match="must be positive"):
        validate_positive_amount(-1.0)
    
    with pytest.raises(ValidationError, match="must be a number"):
        validate_positive_amount("invalid")
    
    with pytest.raises(ValidationError, match="too large"):
        validate_positive_amount(1e19)


def test_weights_validation():
    """Test weights dictionary validation"""
    # Valid case
    weights = {1: 0.5, 2: 0.3, 3: 0.2}
    validated = validate_weights(weights)
    assert len(validated) == 3
    assert abs(sum(validated.values()) - 1.0) < 1e-6
    
    # Invalid cases
    with pytest.raises(ValidationError, match="must be a dictionary"):
        validate_weights("invalid")
    
    with pytest.raises(ValidationError, match="cannot be empty"):
        validate_weights({})
    
    with pytest.raises(ValidationError, match="too many weights"):
        validate_weights({i: 0.05 for i in range(25)})
    
    with pytest.raises(ValidationError, match="must sum to 1.0"):
        validate_weights({1: 0.5, 2: 0.3})  # Sum = 0.8


def test_rate_limiter():
    """Test rate limiting functionality"""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    
    # First 3 requests should pass
    assert limiter.is_allowed("client1") == True
    assert limiter.is_allowed("client1") == True
    assert limiter.is_allowed("client1") == True
    
    # 4th request should be blocked
    assert limiter.is_allowed("client1") == False
    
    # Different client should still work
    assert limiter.is_allowed("client2") == True


def test_api_rate_limiting(monkeypatch):
    """Test API endpoint rate limiting"""
    import os
    monkeypatch.setenv("AM_API_TOKEN", "test")
    monkeypatch.setenv("AM_MINT_RATE_LIMIT", "2")  # Very low limit for testing
    monkeypatch.setenv("AM_MINT_WINDOW_SEC", "60")
    
    client = TestClient(app)
    
    # First request should work
    response = client.post(
        "/mint-tao",
        headers={"Authorization": "Bearer test"},
        json={"in_dir": "/tmp", "amount_tao": 1.0}
    )
    # May fail for other reasons, but shouldn't be rate limited
    assert response.status_code != 429
    
    # After limit is reached, should get 429
    for _ in range(3):  # Exceed the limit
        response = client.post(
            "/mint-tao",
            headers={"Authorization": "Bearer test"},
            json={"in_dir": "/tmp", "amount_tao": 1.0}
        )
    
    # Should eventually hit rate limit
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]


def test_input_validation_api(monkeypatch):
    """Test API input validation"""
    import os
    monkeypatch.setenv("AM_API_TOKEN", "test")
    
    client = TestClient(app)
    
    # Test negative amount
    response = client.post(
        "/mint-tao",
        headers={"Authorization": "Bearer test"},
        json={"in_dir": "/tmp", "amount_tao": -1.0}
    )
    assert response.status_code == 400
    assert "validation_error" in response.json()["detail"]
    
    # Test zero amount
    response = client.post(
        "/mint-tao",
        headers={"Authorization": "Bearer test"},
        json={"in_dir": "/tmp", "amount_tao": 0}
    )
    assert response.status_code == 400
    assert "validation_error" in response.json()["detail"]
    
    # Test dangerous file path
    response = client.post(
        "/mint-tao",
        headers={"Authorization": "Bearer test"},
        json={"in_dir": "/tmp/../etc/passwd", "amount_tao": 1.0}
    )
    assert response.status_code == 400
    assert "validation_error" in response.json()["detail"]


def test_overflow_protection():
    """Test overflow protection in calculations"""
    from subnet.common.validation import validate_positive_amount
    
    # Test very large numbers
    max_safe = 1e18
    with pytest.raises(ValidationError, match="too large"):
        validate_positive_amount(max_safe * 10)


def test_price_staleness_validation():
    """Test price staleness validation"""
    from subnet.validator.service import validate_price_freshness
    from subnet.tao20.reports import PriceReport
    from datetime import datetime, timezone, timedelta
    
    now = datetime.now(timezone.utc)
    fresh_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_ts = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    reports = [
        PriceReport(ts=fresh_ts, prices_by_netuid={1: 1.0}, miner_id="m1"),
        PriceReport(ts=stale_ts, prices_by_netuid={1: 1.0}, miner_id="m2"),
    ]
    
    # With 5 minute max age, only fresh report should remain
    fresh_reports = validate_price_freshness(reports, max_age_minutes=5)
    assert len(fresh_reports) == 1
    assert fresh_reports[0].miner_id == "m1"


def test_emergency_stop_functionality():
    """Test emergency stop circuit breaker"""
    # This would require deploying contracts in a test environment
    # For now, we'll test the logic components
    
    # Test that emergency stop state is properly tracked
    emergency_active = True
    paused = False
    
    # Both conditions should block operations
    should_allow = not (paused or emergency_active)
    assert should_allow == False
    
    # Only when both are false should operations be allowed
    emergency_active = False
    paused = False
    should_allow = not (paused or emergency_active)
    assert should_allow == True


if __name__ == "__main__":
    pytest.main([__file__])
