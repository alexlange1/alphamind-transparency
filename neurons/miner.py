#!/usr/bin/env python3
"""
TAO20 Miner - Authorized Participant for In-Kind Index Creation
Professional entry point with comprehensive configuration and monitoring
"""

import asyncio
import argparse
import os
import sys
import signal

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neurons.miner.miner import TAO20Miner
from common.logging import get_logger


def main():
    """Main entry point for TAO20 miner"""
    parser = argparse.ArgumentParser(
        description="TAO20 Index Miner - Authorized Participant for In-Kind Creation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Wallet configuration
    parser.add_argument("--wallet.name", type=str, default="default", help="Wallet name")
    parser.add_argument("--wallet.hotkey", type=str, default="default", help="Hotkey name") 
    parser.add_argument("--wallet.path", type=str, default="~/.bittensor/wallets", help="Wallet path")
    
    # Network configuration
    parser.add_argument("--subtensor.network", type=str, default="finney", help="Bittensor network")
    parser.add_argument("--netuid", type=int, required=True, help="Subnet netuid")
    
    # TAO20 specific configuration
    parser.add_argument("--tao20.api_url", type=str, default="http://localhost:8000", help="TAO20 API URL")
    parser.add_argument("--tao20.evm_addr", type=str, required=True, help="EVM address for minting")
    parser.add_argument("--tao20.miner_id", type=str, default="tao20_miner", help="Miner identifier")
    
    # Mining configuration
    parser.add_argument("--min_creation_size", type=int, default=1000, help="Minimum creation size")
    parser.add_argument("--creation_interval", type=int, default=60, help="Creation check interval (seconds)")
    parser.add_argument("--dry_run", action="store_true", help="Run in dry-run mode")
    
    # Monitoring configuration (inspired by Sturdy Subnet)
    parser.add_argument("--wandb.off", action="store_true", help="Disable WandB logging")
    parser.add_argument("--wandb.project", type=str, default="alphamind-tao20", help="WandB project name")
    parser.add_argument("--wandb.entity", type=str, help="WandB entity name")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logger = get_logger(
        name="tao20_miner",
        log_level=args.log_level,
        use_wandb=not args.wandb.off,
        wandb_project=args.wandb.project
    )
    
    # Log configuration
    config = {
        "netuid": args.netuid,
        "network": args.subtensor.network,
        "api_url": args.tao20.api_url,
        "evm_addr": args.tao20.evm_addr,
        "miner_id": args.tao20.miner_id,
        "min_creation_size": args.min_creation_size,
        "creation_interval": args.creation_interval,
        "dry_run": args.dry_run
    }
    logger.log_config(config)
    
    # Initialize miner
    try:
        miner = TAO20Miner(
            wallet_path=args.wallet.path,
            source_ss58=None,  # Will use wallet hotkey
            miner_id=args.tao20.miner_id,
            tao20_api_url=args.tao20.api_url,
            evm_addr=args.tao20.evm_addr,
            bittensor_network=args.subtensor.network,
            min_creation_size=args.min_creation_size,
            dry_run=args.dry_run
        )
    except Exception as e:
        logger.error(f"Failed to initialize miner: {e}")
        sys.exit(1)
    
    logger.info("🚀 Starting TAO20 Miner")
    logger.info(f"   Network: {args.subtensor.network}")
    logger.info(f"   Netuid: {args.netuid}")
    logger.info(f"   API URL: {args.tao20.api_url}")
    logger.info(f"   EVM Address: {args.tao20.evm_addr}")
    logger.info(f"   Dry Run: {args.dry_run}")
    
    # Setup graceful shutdown
    stop_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run miner with monitoring
    try:
        asyncio.run(miner.run_creation_loop(
            interval=args.creation_interval,
            stop_event=stop_event
        ))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Miner crashed: {e}")
        sys.exit(1)
    finally:
        logger.info("TAO20 Miner shutdown complete")


if __name__ == "__main__":
    main()
