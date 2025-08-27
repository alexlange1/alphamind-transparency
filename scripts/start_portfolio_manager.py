#!/usr/bin/env python3
"""
TAO20 Automated Portfolio Manager Startup Script

This script provides an easy way to start the automated portfolio management system
with proper configuration and monitoring.
"""

import sys
import os
import asyncio
import logging
import argparse
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from creation.portfolio_scheduler import main as scheduler_main

def setup_logging(log_level: str = "INFO", log_file: str = None):
    """Set up comprehensive logging"""
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Set specific log levels for noisy modules
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

def check_prerequisites():
    """Check that all prerequisites are met"""
    errors = []
    
    # Check btcli is available
    import shutil
    if not shutil.which('btcli'):
        errors.append("btcli command not found in PATH")
    
    # Check Python version
    if sys.version_info < (3, 8):
        errors.append("Python 3.8 or higher required")
    
    # Check required directories exist or can be created
    required_dirs = ['./portfolio_data', './creation_files', './logs']
    for dir_path in required_dirs:
        try:
            Path(dir_path).mkdir(exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create directory {dir_path}: {e}")
    
    if errors:
        print("Prerequisites check failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Start TAO20 Automated Portfolio Manager")
    
    # Portfolio configuration
    parser.add_argument("--btcli-path", default="btcli", 
                       help="Path to btcli executable")
    parser.add_argument("--network", default="finney", 
                       help="Bittensor network (finney, test, local)")
    parser.add_argument("--data-dir", default="./portfolio_data", 
                       help="Data directory for portfolio management")
    parser.add_argument("--config-file", default="./creation/portfolio_config.json",
                       help="Portfolio configuration file")
    
    # Scheduling configuration
    parser.add_argument("--snapshot-hour", type=int, default=0,
                       help="Hour for daily snapshots (UTC, 0-23)")
    parser.add_argument("--snapshot-minute", type=int, default=5,
                       help="Minute for daily snapshots (0-59)")
    
    # Logging configuration
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    parser.add_argument("--log-file", default="./logs/portfolio_manager.log",
                       help="Log file path")
    
    # Operation modes
    parser.add_argument("--check-only", action="store_true",
                       help="Check prerequisites and configuration only")
    parser.add_argument("--status", action="store_true",
                       help="Show status and exit")
    parser.add_argument("--force-snapshot", action="store_true",
                       help="Force immediate snapshot and exit")
    parser.add_argument("--force-publish", action="store_true",
                       help="Force immediate weight publishing and exit")
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting TAO20 Automated Portfolio Manager")
    logger.info(f"Network: {args.network}")
    logger.info(f"Data directory: {args.data_dir}")
    logger.info(f"Configuration file: {args.config_file}")
    
    # Check prerequisites
    if not check_prerequisites():
        logger.error("Prerequisites check failed")
        return 1
    
    logger.info("Prerequisites check passed")
    
    if args.check_only:
        logger.info("Check-only mode: all prerequisites satisfied")
        return 0
    
    # Prepare scheduler arguments
    scheduler_args = [
        "--btcli-path", args.btcli_path,
        "--data-dir", args.data_dir,
        "--network", args.network,
        "--snapshot-hour", str(args.snapshot_hour),
        "--snapshot-minute", str(args.snapshot_minute),
    ]
    
    if args.config_file and os.path.exists(args.config_file):
        scheduler_args.extend(["--config-file", args.config_file])
    
    if args.status:
        scheduler_args.append("--status")
    elif args.force_snapshot:
        scheduler_args.append("--force-snapshot")
    elif args.force_publish:
        scheduler_args.append("--force-publish")
    
    # Override sys.argv to pass arguments to scheduler
    original_argv = sys.argv
    try:
        sys.argv = ["portfolio_scheduler"] + scheduler_args
        result = await scheduler_main()
        return result
    finally:
        sys.argv = original_argv

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
