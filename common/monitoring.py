#!/usr/bin/env python3
"""
Monitoring and alerting utilities for TAO20 protocol
"""
import json
import time
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict


@dataclass
class SecurityAlert:
    """Security alert structure"""
    timestamp: str
    alert_type: str
    severity: str  # "low", "medium", "high", "critical"
    message: str
    context: Dict[str, Any]
    resolved: bool = False


@dataclass
class ProtocolMetrics:
    """Protocol health metrics"""
    timestamp: str
    total_supply: float
    nav_per_token: float
    num_active_miners: int
    num_active_validators: int
    price_deviation_max: float
    consensus_quorum: float
    emergency_stop_active: bool
    paused: bool


class SecurityMonitor:
    """Monitor for security events and anomalies"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.alerts_path = base_path / "security_alerts.jsonl"
        self.metrics_path = base_path / "protocol_metrics.jsonl"
        self.logger = logging.getLogger("security_monitor")
    
    def alert(self, alert_type: str, severity: str, message: str, context: Dict[str, Any] = None):
        """Log a security alert"""
        alert = SecurityAlert(
            timestamp=datetime.now(timezone.utc).isoformat(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            context=context or {},
        )
        
        # Log to file
        try:
            with open(self.alerts_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(alert), separators=(",", ":")) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write security alert: {e}")
        
        # Log to standard logger
        if severity == "critical":
            self.logger.critical(f"SECURITY ALERT: {message}")
        elif severity == "high":
            self.logger.error(f"SECURITY ALERT: {message}")
        elif severity == "medium":
            self.logger.warning(f"SECURITY ALERT: {message}")
        else:
            self.logger.info(f"SECURITY ALERT: {message}")
    
    def record_metrics(self, metrics: ProtocolMetrics):
        """Record protocol health metrics"""
        try:
            with open(self.metrics_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(metrics), separators=(",", ":")) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write metrics: {e}")
    
    def check_price_manipulation(self, prices: Dict[int, float], expected_prices: Dict[int, float], 
                                threshold_pct: float = 20.0):
        """Check for potential price manipulation"""
        for netuid, price in prices.items():
            expected = expected_prices.get(netuid)
            if expected and expected > 0:
                deviation_pct = abs(price - expected) / expected * 100
                if deviation_pct > threshold_pct:
                    self.alert(
                        "price_manipulation",
                        "high",
                        f"Large price deviation detected for netuid {netuid}",
                        {
                            "netuid": netuid,
                            "current_price": price,
                            "expected_price": expected,
                            "deviation_pct": deviation_pct
                        }
                    )
    
    def check_consensus_quorum(self, quorum_pct: float, min_quorum: float = 33.0):
        """Check if consensus quorum is sufficient"""
        if quorum_pct < min_quorum:
            self.alert(
                "low_quorum",
                "medium",
                f"Consensus quorum below threshold: {quorum_pct:.1f}%",
                {"quorum_pct": quorum_pct, "min_required": min_quorum}
            )
    
    def check_rate_limit_abuse(self, client_requests: Dict[str, int], threshold: int = 100):
        """Check for potential rate limit abuse"""
        for client_ip, request_count in client_requests.items():
            if request_count > threshold:
                self.alert(
                    "rate_limit_abuse",
                    "medium",
                    f"High request volume from client: {client_ip}",
                    {"client_ip": client_ip, "request_count": request_count}
                )
    
    def check_emergency_conditions(self, nav_change_pct: float, max_change: float = 10.0):
        """Check for conditions requiring emergency stop"""
        if abs(nav_change_pct) > max_change:
            self.alert(
                "emergency_nav_change",
                "critical",
                f"Large NAV change detected: {nav_change_pct:.2f}%",
                {"nav_change_pct": nav_change_pct}
            )
    
    def get_recent_alerts(self, hours: int = 24) -> List[SecurityAlert]:
        """Get recent security alerts"""
        alerts = []
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        
        try:
            if self.alerts_path.exists():
                with open(self.alerts_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            alert_data = json.loads(line.strip())
                            alert_time = datetime.fromisoformat(alert_data["timestamp"]).timestamp()
                            if alert_time >= cutoff_time:
                                alerts.append(SecurityAlert(**alert_data))
                        except Exception:
                            continue
        except Exception as e:
            self.logger.error(f"Failed to read alerts: {e}")
        
        return alerts


def create_monitoring_dashboard_data(base_path: Path) -> Dict[str, Any]:
    """Create data for monitoring dashboard"""
    monitor = SecurityMonitor(base_path)
    recent_alerts = monitor.get_recent_alerts(24)
    
    # Count alerts by severity
    alert_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for alert in recent_alerts:
        alert_counts[alert.severity] = alert_counts.get(alert.severity, 0) + 1
    
    # Get latest metrics
    latest_metrics = None
    try:
        if monitor.metrics_path.exists():
            with open(monitor.metrics_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    latest_metrics = json.loads(lines[-1].strip())
    except Exception:
        pass
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alert_summary": alert_counts,
        "latest_metrics": latest_metrics,
        "recent_alerts": [asdict(alert) for alert in recent_alerts[-10:]],  # Last 10 alerts
        "system_status": "healthy" if alert_counts["critical"] == 0 else "degraded"
    }


def check_system_health(base_path: Path) -> Dict[str, Any]:
    """Comprehensive system health check"""
    health_status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "healthy",
        "checks": {}
    }
    
    # Check if critical files exist
    critical_files = ["vault_state.json", "weights.json"]
    for filename in critical_files:
        file_path = base_path / filename
        health_status["checks"][f"file_{filename}"] = {
            "status": "ok" if file_path.exists() else "error",
            "message": f"File {filename} {'exists' if file_path.exists() else 'missing'}"
        }
        if not file_path.exists():
            health_status["overall_status"] = "degraded"
    
    # Check for recent activity
    emissions_files = list(base_path.glob("emissions_*_*.json"))
    price_files = list(base_path.glob("prices_*_*.json"))
    
    health_status["checks"]["recent_emissions"] = {
        "status": "ok" if len(emissions_files) > 0 else "warning",
        "message": f"Found {len(emissions_files)} emission reports"
    }
    
    health_status["checks"]["recent_prices"] = {
        "status": "ok" if len(price_files) > 0 else "warning", 
        "message": f"Found {len(price_files)} price reports"
    }
    
    # Check for alerts
    monitor = SecurityMonitor(base_path)
    critical_alerts = [a for a in monitor.get_recent_alerts(1) if a.severity == "critical"]
    
    health_status["checks"]["security_alerts"] = {
        "status": "error" if critical_alerts else "ok",
        "message": f"Found {len(critical_alerts)} critical alerts in last hour"
    }
    
    if critical_alerts:
        health_status["overall_status"] = "error"
    
    return health_status
