#!/usr/bin/env python3
"""
Portfolio Scheduler Service for TAO20

This service provides precise scheduling for automated portfolio management:
1. Daily emissions snapshots at exactly 00:00 UTC
2. Epoch boundary weight publishing 
3. Robust error handling and recovery
4. Comprehensive monitoring and alerting

The scheduler ensures deterministic, un-gameable timing that cannot be manipulated.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import json
import os
from pathlib import Path

try:
    from .automated_portfolio_manager import AutomatedPortfolioManager, WeightingConfig
    from ..sim.epoch import current_epoch_id, EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    
    from creation.automated_portfolio_manager import AutomatedPortfolioManager, WeightingConfig
    from sim.epoch import current_epoch_id, EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS

logger = logging.getLogger(__name__)

class PortfolioScheduler:
    """
    High-precision scheduler for automated portfolio management
    
    Features:
    - UTC-based deterministic scheduling
    - Automatic recovery from failures
    - Comprehensive monitoring
    - Graceful shutdown handling
    """
    
    def __init__(
        self,
        portfolio_manager: AutomatedPortfolioManager,
        snapshot_hour: int = 0,  # 00:00 UTC
        snapshot_minute: int = 5,  # 00:05 UTC (small delay for system stability)
        max_retry_attempts: int = 3,
        retry_delay_minutes: int = 30
    ):
        self.portfolio_manager = portfolio_manager
        self.snapshot_hour = snapshot_hour
        self.snapshot_minute = snapshot_minute
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_minutes = retry_delay_minutes
        
        # State tracking
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        self.last_successful_snapshot: Optional[str] = None
        self.last_successful_publish: Optional[int] = None
        
        # Statistics
        self.stats = {
            'snapshots_taken': 0,
            'snapshots_failed': 0,
            'weights_published': 0,
            'weight_publish_failed': 0,
            'uptime_start': None,
            'last_activity': None
        }
        
        logger.info(f"PortfolioScheduler initialized")
        logger.info(f"Daily snapshots scheduled for {snapshot_hour:02d}:{snapshot_minute:02d} UTC")
    
    async def start(self):
        """Start the scheduler service"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return
        
        self.is_running = True
        self.stats['uptime_start'] = datetime.now(timezone.utc).isoformat()
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        logger.info("Portfolio scheduler started")
        logger.info(f"Current epoch: {current_epoch_id()}")
        
        try:
            # Run main scheduling loop
            await self._run_scheduling_loop()
        except Exception as e:
            logger.error(f"Scheduler failed: {e}")
            raise
        finally:
            self.is_running = False
            logger.info("Portfolio scheduler stopped")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_event.set()
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except Exception as e:
            logger.warning(f"Could not set up signal handlers: {e}")
    
    async def _run_scheduling_loop(self):
        """Main scheduling loop"""
        logger.info("Starting scheduling loop...")
        
        # Initial checks on startup
        await self._check_and_handle_missed_activities()
        
        while not self.shutdown_event.is_set():
            try:
                # Calculate next scheduled activity
                next_snapshot_time = self._get_next_snapshot_time()
                next_epoch_boundary = self._get_next_epoch_boundary()
                
                # Determine which event comes first
                now = datetime.now(timezone.utc)
                
                if next_snapshot_time <= next_epoch_boundary:
                    # Snapshot comes first
                    wait_seconds = (next_snapshot_time - now).total_seconds()
                    activity_type = "snapshot"
                    activity_time = next_snapshot_time
                else:
                    # Epoch boundary comes first
                    wait_seconds = (next_epoch_boundary - now).total_seconds()
                    activity_type = "publish"
                    activity_time = next_epoch_boundary
                
                if wait_seconds > 0:
                    logger.info(f"Next {activity_type} scheduled for {activity_time.isoformat()}")
                    logger.info(f"Waiting {wait_seconds:.0f} seconds...")
                    
                    # Wait with periodic health checks
                    await self._wait_with_health_checks(wait_seconds)
                
                if self.shutdown_event.is_set():
                    break
                
                # Execute the scheduled activity
                if activity_type == "snapshot":
                    await self._execute_daily_snapshot()
                else:
                    await self._execute_weight_publishing()
                
            except asyncio.CancelledError:
                logger.info("Scheduling loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduling loop: {e}")
                # Wait before retrying to avoid tight error loops
                await asyncio.sleep(60)
    
    async def _wait_with_health_checks(self, wait_seconds: float):
        """Wait with periodic health checks and status logging"""
        check_interval = 3600  # Check every hour
        total_waited = 0
        
        while total_waited < wait_seconds and not self.shutdown_event.is_set():
            sleep_time = min(check_interval, wait_seconds - total_waited)
            
            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=sleep_time)
                break  # Shutdown requested
            except asyncio.TimeoutError:
                # Normal timeout, continue waiting
                total_waited += sleep_time
                
                # Log health check
                remaining = wait_seconds - total_waited
                logger.info(f"Health check: {remaining:.0f} seconds until next activity")
    
    def _get_next_snapshot_time(self) -> datetime:
        """Calculate next daily snapshot time"""
        now = datetime.now(timezone.utc)
        
        # Calculate today's snapshot time
        today_snapshot = now.replace(
            hour=self.snapshot_hour, 
            minute=self.snapshot_minute, 
            second=0, 
            microsecond=0
        )
        
        if now >= today_snapshot:
            # Today's snapshot has passed, schedule for tomorrow
            return today_snapshot + timedelta(days=1)
        else:
            # Today's snapshot is still upcoming
            return today_snapshot
    
    def _get_next_epoch_boundary(self) -> datetime:
        """Calculate next epoch boundary"""
        now_unix = int(datetime.now(timezone.utc).timestamp())
        current_epoch = current_epoch_id(now_unix)
        next_epoch_start_unix = EPOCH_ANCHOR_UNIX + (current_epoch + 1) * REBALANCE_PERIOD_SECS
        return datetime.fromtimestamp(next_epoch_start_unix, tz=timezone.utc)
    
    async def _check_and_handle_missed_activities(self):
        """Check for and handle any missed activities on startup"""
        logger.info("Checking for missed activities...")
        
        # Check for missed snapshots
        current_day = datetime.now(timezone.utc).date().isoformat()
        manager_last_day = self.portfolio_manager.last_snapshot_day
        
        if manager_last_day != current_day:
            logger.info(f"Missed snapshot detected. Last: {manager_last_day}, Current: {current_day}")
            # Take snapshot immediately if we're in the acceptable window
            now = datetime.now(timezone.utc)
            if now.hour < 12:  # Only catch up if it's still morning UTC
                logger.info("Taking catch-up snapshot...")
                await self._execute_daily_snapshot()
        
        # Check for missed weight publishing
        current_epoch = current_epoch_id()
        manager_last_epoch = self.portfolio_manager.last_weight_publish_epoch
        
        if manager_last_epoch is None or current_epoch > manager_last_epoch:
            logger.info(f"Missed weight publishing detected. Last: {manager_last_epoch}, Current: {current_epoch}")
            await self._execute_weight_publishing()
    
    async def _execute_daily_snapshot(self):
        """Execute daily emissions snapshot with retry logic"""
        logger.info("Executing daily emissions snapshot...")
        self.stats['last_activity'] = datetime.now(timezone.utc).isoformat()
        
        for attempt in range(1, self.max_retry_attempts + 1):
            try:
                snapshot = await self.portfolio_manager.take_daily_snapshot()
                
                if snapshot:
                    self.stats['snapshots_taken'] += 1
                    self.last_successful_snapshot = snapshot.snapshot_time
                    logger.info(f"Daily snapshot completed successfully on attempt {attempt}")
                    logger.info(f"Diversification score: {snapshot.diversification_score:.3f}")
                    return
                else:
                    raise Exception("Snapshot returned None")
                    
            except Exception as e:
                logger.error(f"Snapshot attempt {attempt} failed: {e}")
                
                if attempt < self.max_retry_attempts:
                    wait_minutes = self.retry_delay_minutes * attempt
                    logger.info(f"Retrying in {wait_minutes} minutes...")
                    await asyncio.sleep(wait_minutes * 60)
                else:
                    logger.error("All snapshot attempts failed")
                    self.stats['snapshots_failed'] += 1
    
    async def _execute_weight_publishing(self):
        """Execute weight publishing with retry logic"""
        logger.info("Executing weight publishing...")
        self.stats['last_activity'] = datetime.now(timezone.utc).isoformat()
        
        for attempt in range(1, self.max_retry_attempts + 1):
            try:
                published = await self.portfolio_manager.publish_weights_if_needed()
                
                if published:
                    self.stats['weights_published'] += 1
                    self.last_successful_publish = current_epoch_id()
                    logger.info(f"Weight publishing completed successfully on attempt {attempt}")
                    return
                else:
                    logger.info("No weight publishing needed (already up to date)")
                    return
                    
            except Exception as e:
                logger.error(f"Weight publishing attempt {attempt} failed: {e}")
                
                if attempt < self.max_retry_attempts:
                    wait_minutes = self.retry_delay_minutes * attempt
                    logger.info(f"Retrying in {wait_minutes} minutes...")
                    await asyncio.sleep(wait_minutes * 60)
                else:
                    logger.error("All weight publishing attempts failed")
                    self.stats['weight_publish_failed'] += 1
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduler status"""
        now = datetime.now(timezone.utc)
        
        status = {
            'is_running': self.is_running,
            'current_time': now.isoformat(),
            'current_epoch': current_epoch_id(),
            'next_snapshot': self._get_next_snapshot_time().isoformat(),
            'next_epoch_boundary': self._get_next_epoch_boundary().isoformat(),
            'last_successful_snapshot': self.last_successful_snapshot,
            'last_successful_publish': self.last_successful_publish,
            'statistics': self.stats.copy()
        }
        
        # Calculate uptime
        if self.stats['uptime_start']:
            uptime_start = datetime.fromisoformat(self.stats['uptime_start'].replace('Z', '+00:00'))
            uptime_seconds = (now - uptime_start).total_seconds()
            status['uptime_hours'] = uptime_seconds / 3600
        
        return status
    
    async def force_snapshot(self) -> bool:
        """Force an immediate snapshot (for testing/manual intervention)"""
        logger.info("Forcing immediate snapshot...")
        try:
            snapshot = await self.portfolio_manager.take_daily_snapshot()
            return snapshot is not None
        except Exception as e:
            logger.error(f"Forced snapshot failed: {e}")
            return False
    
    async def force_weight_publishing(self) -> bool:
        """Force immediate weight publishing (for testing/manual intervention)"""
        logger.info("Forcing immediate weight publishing...")
        try:
            return await self.portfolio_manager.publish_weights_if_needed()
        except Exception as e:
            logger.error(f"Forced weight publishing failed: {e}")
            return False
    
    async def stop(self):
        """Stop the scheduler gracefully"""
        logger.info("Stopping portfolio scheduler...")
        self.shutdown_event.set()
        
        # Give some time for graceful shutdown
        try:
            await asyncio.wait_for(self._wait_for_shutdown(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning("Graceful shutdown timeout, forcing stop")
    
    async def _wait_for_shutdown(self):
        """Wait for scheduler to fully shut down"""
        while self.is_running:
            await asyncio.sleep(0.1)


async def main():
    """Main entry point for portfolio scheduler service"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TAO20 Portfolio Scheduler Service")
    parser.add_argument("--btcli-path", default="btcli", help="Path to btcli executable")
    parser.add_argument("--data-dir", default="./portfolio_data", help="Data directory")
    parser.add_argument("--network", default="finney", help="Bittensor network")
    parser.add_argument("--snapshot-hour", type=int, default=0, help="Hour for daily snapshots (UTC)")
    parser.add_argument("--snapshot-minute", type=int, default=5, help="Minute for daily snapshots (UTC)")
    parser.add_argument("--config-file", help="Portfolio configuration file")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--force-snapshot", action="store_true", help="Force immediate snapshot")
    parser.add_argument("--force-publish", action="store_true", help="Force immediate weight publishing")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('portfolio_scheduler.log')
        ]
    )
    
    # Load configuration
    config = WeightingConfig()
    if args.config_file and os.path.exists(args.config_file):
        try:
            with open(args.config_file, 'r') as f:
                config_data = json.load(f)
            config = WeightingConfig(**config_data)
            logger.info(f"Loaded configuration from {args.config_file}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return 1
    
    # Initialize portfolio manager
    portfolio_manager = AutomatedPortfolioManager(
        btcli_path=args.btcli_path,
        data_dir=args.data_dir,
        network=args.network,
        config=config
    )
    
    # Initialize scheduler
    scheduler = PortfolioScheduler(
        portfolio_manager=portfolio_manager,
        snapshot_hour=args.snapshot_hour,
        snapshot_minute=args.snapshot_minute
    )
    
    # Handle different modes
    if args.status:
        # Status mode
        status = scheduler.get_status()
        portfolio_stats = portfolio_manager.get_portfolio_stats()
        
        print("=== Portfolio Scheduler Status ===")
        print(json.dumps(status, indent=2))
        print("\n=== Portfolio Statistics ===")
        print(json.dumps(portfolio_stats, indent=2))
        return 0
    
    elif args.force_snapshot:
        # Force snapshot mode
        success = await scheduler.force_snapshot()
        print(f"Forced snapshot: {'SUCCESS' if success else 'FAILED'}")
        return 0 if success else 1
    
    elif args.force_publish:
        # Force publishing mode
        success = await scheduler.force_weight_publishing()
        print(f"Forced weight publishing: {'SUCCESS' if success else 'FAILED'}")
        return 0 if success else 1
    
    else:
        # Normal service mode
        try:
            await scheduler.start()
            return 0
        except KeyboardInterrupt:
            logger.info("Service interrupted by user")
            return 0
        except Exception as e:
            logger.error(f"Service failed: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
