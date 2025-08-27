#!/usr/bin/env python3
"""
TAO20 Validator - Creation Receipt Validator and NAV Calculator
"""

import asyncio
import argparse
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neurons.validator.validator import TAO20Validator


def main():
    """Main entry point for TAO20 validator"""
    parser = argparse.ArgumentParser(description="TAO20 Index Validator")
    
    # Wallet configuration
    parser.add_argument("--wallet.name", type=str, default="default", help="Wallet name")
    parser.add_argument("--wallet.hotkey", type=str, default="default", help="Hotkey name")
    parser.add_argument("--wallet.path", type=str, default="~/.bittensor/wallets", help="Wallet path")
    
    # Network configuration
    parser.add_argument("--subtensor.network", type=str, default="finney", help="Bittensor network")
    parser.add_argument("--netuid", type=int, required=True, help="Subnet netuid")
    
    # TAO20 specific configuration
    parser.add_argument("--tao20.api_url", type=str, default="http://localhost:8000", help="TAO20 API URL")
    parser.add_argument("--tao20.validator_id", type=str, default="tao20_validator", help="Validator identifier")
    
    # Validation configuration
    parser.add_argument("--min_attestation_interval", type=int, default=60, help="Minimum attestation interval")
    parser.add_argument("--max_creation_age", type=int, default=3600, help="Maximum creation age")
    parser.add_argument("--monitoring_interval", type=int, default=30, help="Creation monitoring interval")
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = TAO20Validator(
        wallet_path=args.wallet.path,
        source_ss58=None,  # Will use wallet hotkey
        validator_id=args.tao20.validator_id,
        tao20_api_url=args.tao20.api_url,
        bittensor_network=args.subtensor.network,
        min_attestation_interval=args.min_attestation_interval,
        max_creation_age=args.max_creation_age
    )
    
    print(f"🛡️  Starting TAO20 Validator")
    print(f"   Network: {args.subtensor.network}")
    print(f"   Netuid: {args.netuid}")
    print(f"   API URL: {args.tao20.api_url}")
    print(f"   Validator ID: {args.tao20.validator_id}")
    
    # Run validator
    asyncio.run(validator.run_bittensor_validator())


if __name__ == "__main__":
    main()
