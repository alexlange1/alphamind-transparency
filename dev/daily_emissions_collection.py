#!/usr/bin/env python3
"""
Daily Automated Emissions Collection Script

This script should be run daily at a fixed time (e.g., 4 PM UTC) via cron
to collect emissions data from the Bittensor network automatically.

Usage:
    python3 scripts/daily_emissions_collection.py

Cron entry example (4 PM UTC daily):
    0 16 * * * cd /path/to/alphamind && python3 scripts/daily_emissions_collection.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from emissions.snapshot import schedule_daily_emissions_collection
from common.settings import get_settings


def main():
    """Main entry point for daily emissions collection"""
    try:
        print(f"=== Daily Emissions Collection Started ===")
        print(f"Time: {datetime.now(timezone.utc).isoformat()}")
        
        # Get settings
        settings = get_settings()
        out_dir = Path(settings.out_dir)
        btcli_path = settings.btcli_path
        network = os.environ.get("BITTENSOR_NETWORK", "finney")
        
        print(f"Output directory: {out_dir}")
        print(f"btcli path: {btcli_path}")
        print(f"Network: {network}")
        
        # Ensure output directory exists
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Run daily emissions collection
        schedule_daily_emissions_collection(
            out_dir=out_dir,
            btcli_path=btcli_path,
            network=network,
            collection_hour_utc=16  # 4 PM UTC
        )
        
        print("=== Daily Emissions Collection Completed ===")
        return 0
        
    except Exception as e:
        print(f"❌ Error during daily emissions collection: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
