#!/usr/bin/env python3
"""
Tests for core security functions (without API dependencies)
"""
import pytest
from pathlib import Path
import tempfile
import json
import time


def test_input_validation_positive_amounts():
    """Test positive amount validation"""
    from subnet.common.validation import ValidationError, validate_positive_amount
    
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
    from subnet.common.validation import ValidationError, validate_weights
    
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
    from subnet.common.rate_limiter import RateLimiter
    
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    
    # First 3 requests should pass
    assert limiter.is_allowed("client1") == True
    assert limiter.is_allowed("client1") == True
    assert limiter.is_allowed("client1") == True
    
    # 4th request should be blocked
    assert limiter.is_allowed("client1") == False
    
    # Different client should still work
    assert limiter.is_allowed("client2") == True


def test_file_path_sanitization():
    """Test file path sanitization"""
    from subnet.common.validation import ValidationError, sanitize_file_path
    
    # Valid paths
    assert sanitize_file_path("/tmp/valid") == "/tmp/valid"
    assert sanitize_file_path("relative/path") == "relative/path"
    
    # Invalid paths
    with pytest.raises(ValidationError, match="dangerous pattern"):
        sanitize_file_path("/tmp/../etc/passwd")
    
    with pytest.raises(ValidationError, match="dangerous pattern"):
        sanitize_file_path("/tmp/file~backup")
    
    with pytest.raises(ValidationError, match="dangerous pattern"):
        sanitize_file_path("/tmp/file$var")


def test_netuid_validation():
    """Test subnet ID validation"""
    from subnet.common.validation import ValidationError, validate_netuid
    
    # Valid cases
    assert validate_netuid(1) == 1
    assert validate_netuid(999) == 999
    
    # Invalid cases
    with pytest.raises(ValidationError, match="must be an integer"):
        validate_netuid("invalid")
    
    with pytest.raises(ValidationError, match="out of bounds"):
        validate_netuid(-1)
    
    with pytest.raises(ValidationError, match="out of bounds"):
        validate_netuid(1001)


def test_percentage_bps_validation():
    """Test basis points validation"""
    from subnet.common.validation import ValidationError, validate_percentage_bps
    
    # Valid cases
    assert validate_percentage_bps(0) == 0
    assert validate_percentage_bps(5000) == 5000  # 50%
    assert validate_percentage_bps(10000) == 10000  # 100%
    
    # Invalid cases
    with pytest.raises(ValidationError, match="must be an integer"):
        validate_percentage_bps(50.5)
    
    with pytest.raises(ValidationError, match="between 0 and 10000"):
        validate_percentage_bps(-1)
    
    with pytest.raises(ValidationError, match="between 0 and 10000"):
        validate_percentage_bps(10001)


def test_prices_validation():
    """Test price dictionary validation"""
    from subnet.common.validation import ValidationError, validate_prices
    
    # Valid case
    prices = {1: 1.5, 2: 2.0, 3: 0.5}
    validated = validate_prices(prices)
    assert len(validated) == 3
    assert all(v > 0 for v in validated.values())
    
    # Invalid cases
    with pytest.raises(ValidationError, match="must be a dictionary"):
        validate_prices("invalid")
    
    with pytest.raises(ValidationError, match="cannot be empty"):
        validate_prices({})
    
    with pytest.raises(ValidationError, match="must be positive"):
        validate_prices({1: -1.0})


def test_basket_validation():
    """Test in-kind basket validation"""
    from subnet.common.validation import ValidationError, validate_basket
    
    # Valid case
    basket = {1: 10.0, 2: 5.0}
    validated = validate_basket(basket)
    assert len(validated) == 2
    assert all(v > 0 for v in validated.values())
    
    # Invalid cases
    with pytest.raises(ValidationError, match="must be a dictionary"):
        validate_basket("invalid")
    
    with pytest.raises(ValidationError, match="cannot be empty"):
        validate_basket({})
    
    with pytest.raises(ValidationError, match="basket too large"):
        validate_basket({i: 1.0 for i in range(25)})


def test_ss58_address_validation():
    """Test SS58 address validation"""
    from subnet.common.validation import ValidationError, validate_ss58_address
    
    # Valid-looking SS58 address (simplified check)
    valid_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    assert validate_ss58_address(valid_address) == valid_address
    
    # Invalid cases
    with pytest.raises(ValidationError, match="must be a string"):
        validate_ss58_address(123)
    
    with pytest.raises(ValidationError, match="invalid SS58 address length"):
        validate_ss58_address("short")
    
    with pytest.raises(ValidationError, match="invalid SS58 address characters"):
        validate_ss58_address("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQ0")  # Contains '0'


def test_security_monitor():
    """Test security monitoring functionality"""
    from subnet.common.monitoring import SecurityMonitor, SecurityAlert
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        monitor = SecurityMonitor(base_path)
        
        # Test alert creation
        monitor.alert(
            "test_alert",
            "medium",
            "Test security alert",
            {"test_field": "test_value"}
        )
        
        # Check alert was written
        alerts_file = base_path / "security_alerts.jsonl"
        assert alerts_file.exists()
        
        # Read and verify alert
        with open(alerts_file, "r") as f:
            alert_data = json.loads(f.read().strip())
            assert alert_data["alert_type"] == "test_alert"
            assert alert_data["severity"] == "medium"
            assert alert_data["message"] == "Test security alert"


def test_system_health_check():
    """Test system health checking"""
    from subnet.common.monitoring import check_system_health
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        
        # Test without critical files
        health = check_system_health(base_path)
        assert health["overall_status"] == "degraded"
        
        # Create critical files
        (base_path / "vault_state.json").write_text('{"test": true}')
        (base_path / "weights.json").write_text('{"test": true}')
        
        # Test with critical files
        health = check_system_health(base_path)
        assert health["overall_status"] in ["healthy", "degraded"]  # May be degraded due to missing reports


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


def test_overflow_protection():
    """Test overflow protection in calculations"""
    from subnet.common.validation import validate_positive_amount, ValidationError
    
    # Test very large numbers
    max_safe = 1e18
    with pytest.raises(ValidationError, match="too large"):
        validate_positive_amount(max_safe * 10)


if __name__ == "__main__":
    pytest.main([__file__])
