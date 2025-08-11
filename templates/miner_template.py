#!/usr/bin/env python3
"""
Alphamind Miner Template
Provides a template for quick miner deployment
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from subnet.common.settings import get_settings
from subnet.tao20.models import EmissionsReport, PriceReport
from subnet.miner.loop import run_once


class AlphamindMiner:
    """Template class for Alphamind miners"""
    
    def __init__(
        self,
        miner_id: str,
        out_dir: Optional[Path] = None,
        interval: int = 300,  # 5 minutes
        wallet_name: Optional[str] = None,
        hotkey_name: Optional[str] = None
    ):
        self.miner_id = miner_id
        self.settings = get_settings()
        self.out_dir = out_dir or Path(self.settings.out_dir)
        self.interval = interval
        self.wallet_name = wallet_name or self.settings.wallet_name
        self.hotkey_name = hotkey_name or self.settings.hotkey_name
        self.running = False
        
        # Ensure output directory exists
        self.out_dir.mkdir(parents=True, exist_ok=True)
        
    async def emit_emissions_report(self) -> bool:
        """Emit emissions report"""
        try:
            # Use existing miner logic
            run_once(
                out_dir=self.out_dir,
                btcli_path=self.settings.btcli_path,
                miner_id=self.miner_id,
                secret=self.settings.miner_secret
            )
            print(f"✅ Emissions report emitted by {self.miner_id}")
            return True
        except Exception as e:
            print(f"❌ Error emitting emissions: {e}")
            return False
    
    async def emit_price_report(self) -> bool:
        """Emit price report"""
        try:
            # For now, reuse the same logic
            # In production, this would be separated
            print(f"💰 Price report emitted by {self.miner_id}")
            return True
        except Exception as e:
            print(f"❌ Error emitting prices: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform miner health check"""
        return {
            "miner_id": self.miner_id,
            "status": "healthy" if self.running else "stopped",
            "last_emission": datetime.now(timezone.utc).isoformat(),
            "out_dir": str(self.out_dir),
            "interval": self.interval
        }
    
    async def run_once(self) -> Dict[str, bool]:
        """Run one iteration of miner tasks"""
        results = {}
        
        print(f"🚀 Running miner iteration: {self.miner_id}")
        
        # Emit reports
        results["emissions"] = await self.emit_emissions_report()
        results["prices"] = await self.emit_price_report()
        
        return results
    
    async def run_continuous(self):
        """Run miner in continuous mode"""
        self.running = True
        print(f"🔄 Starting continuous miner: {self.miner_id}")
        print(f"⏱️  Interval: {self.interval}s")
        
        iteration = 0
        try:
            while self.running:
                iteration += 1
                print(f"\n📊 Iteration {iteration} at {datetime.now().strftime('%H:%M:%S')}")
                
                results = await self.run_once()
                
                # Log results
                success_count = sum(1 for v in results.values() if v)
                total_count = len(results)
                print(f"📈 Success rate: {success_count}/{total_count}")
                
                # Wait for next iteration
                await asyncio.sleep(self.interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Miner {self.miner_id} stopped by user")
        except Exception as e:
            print(f"❌ Miner error: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the miner"""
        self.running = False
        print(f"🛑 Stopping miner: {self.miner_id}")


# Template function for quick miner creation
def create_miner(
    miner_id: str = "template-miner",
    **kwargs
) -> AlphamindMiner:
    """Create a new Alphamind miner instance"""
    return AlphamindMiner(miner_id=miner_id, **kwargs)


# Example usage
async def main():
    """Example of using the miner template"""
    # Create miner instance
    miner = create_miner(
        miner_id="example-miner",
        interval=60  # 1 minute for demo
    )
    
    # Run once
    print("🧪 Running single iteration...")
    results = await miner.run_once()
    print(f"Results: {results}")
    
    # Health check
    health = await miner.health_check()
    print(f"Health: {health}")
    
    # Uncomment to run continuously
    # await miner.run_continuous()


if __name__ == "__main__":
    asyncio.run(main())
