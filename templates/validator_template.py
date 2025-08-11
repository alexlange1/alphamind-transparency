#!/usr/bin/env python3
"""
Alphamind Validator Template
Provides a template for quick validator deployment
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from subnet.common.settings import get_settings
from subnet.validator.service import aggregate_and_emit, consensus_prices_with_twap
from subnet.validator.scoring import apply_deviation
from subnet.sim.vault import VaultState, compute_nav


class AlphamindValidator:
    """Template class for Alphamind validators"""
    
    def __init__(
        self,
        validator_id: str,
        in_dir: Optional[Path] = None,
        out_dir: Optional[Path] = None,
        top_n: int = 20
    ):
        self.validator_id = validator_id
        self.settings = get_settings()
        self.in_dir = in_dir or Path(self.settings.in_dir)
        self.out_dir = out_dir or Path(self.settings.out_dir)
        self.top_n = top_n
        self.running = False
        
        # Ensure directories exist
        self.in_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize state
        self.last_aggregation = None
        self.last_weights = {}
        
    async def aggregate_reports(self) -> Dict[str, Any]:
        """Aggregate miner reports into index weights"""
        try:
            output_file = self.out_dir / "weightset_latest.json"
            
            print(f"📊 Aggregating reports for validator {self.validator_id}")
            aggregate_and_emit(self.in_dir, output_file, self.top_n)
            
            # Load results
            if output_file.exists():
                with open(output_file) as f:
                    data = json.load(f)
                    weights = data.get("weights", {})
                    
                self.last_weights = weights
                self.last_aggregation = datetime.now(timezone.utc)
                
                return {
                    "success": True,
                    "weights_count": len(weights),
                    "total_weight": sum(weights.values()),
                    "timestamp": self.last_aggregation.isoformat()
                }
            else:
                return {"success": False, "error": "Output file not created"}
                
        except Exception as e:
            print(f"❌ Error aggregating reports: {e}")
            return {"success": False, "error": str(e)}
    
    async def score_miners(self) -> Dict[str, Any]:
        """Score miner performance and apply penalties"""
        try:
            print(f"📊 Scoring miners for validator {self.validator_id}")
            
            # This would implement the full scoring logic
            # For now, return a placeholder
            return {
                "success": True,
                "miners_scored": 0,
                "penalties_applied": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error scoring miners: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_vault_state(self) -> Dict[str, Any]:
        """Update vault simulation state"""
        try:
            vault_state_file = self.out_dir / "vault_state.json"
            
            # Load or initialize vault state
            if vault_state_file.exists():
                with open(vault_state_file) as f:
                    state_data = json.load(f)
                    state = VaultState.from_json(json.dumps(state_data))
            else:
                state = VaultState(holdings={}, tao20_supply=0.0, last_nav_tao=0.0)
            
            # Load current prices
            prices_file = self.out_dir / "prices.json"
            if prices_file.exists():
                with open(prices_file) as f:
                    prices_data = json.load(f)
                    prices = {int(k): float(v) for k, v in prices_data.get("prices", {}).items()}
            else:
                prices = {}
            
            # Calculate NAV if we have prices
            nav = compute_nav(prices, state) if prices else 0.0
            state.last_nav_tao = nav
            
            # Save updated state
            with open(vault_state_file, "w") as f:
                json.dump(json.loads(state.to_json()), f, indent=2)
            
            return {
                "success": True,
                "nav": nav,
                "supply": state.tao20_supply,
                "holdings_count": len(state.holdings),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error updating vault state: {e}")
            return {"success": False, "error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform validator health check"""
        return {
            "validator_id": self.validator_id,
            "status": "healthy" if self.running else "stopped",
            "last_aggregation": self.last_aggregation.isoformat() if self.last_aggregation else None,
            "weights_count": len(self.last_weights),
            "in_dir": str(self.in_dir),
            "out_dir": str(self.out_dir),
            "top_n": self.top_n
        }
    
    async def run_once(self) -> Dict[str, Any]:
        """Run one iteration of validator tasks"""
        print(f"🚀 Running validator iteration: {self.validator_id}")
        
        results = {}
        
        # 1. Aggregate reports
        results["aggregation"] = await self.aggregate_reports()
        
        # 2. Score miners
        results["scoring"] = await self.score_miners()
        
        # 3. Update vault state
        results["vault_update"] = await self.update_vault_state()
        
        return results
    
    async def run_continuous(self, interval: int = 300):
        """Run validator in continuous mode"""
        self.running = True
        print(f"🔄 Starting continuous validator: {self.validator_id}")
        print(f"⏱️  Interval: {interval}s")
        
        iteration = 0
        try:
            while self.running:
                iteration += 1
                print(f"\n📊 Validator iteration {iteration} at {datetime.now().strftime('%H:%M:%S')}")
                
                results = await self.run_once()
                
                # Log results summary
                success_count = sum(1 for r in results.values() if r.get("success", False))
                total_count = len(results)
                print(f"📈 Success rate: {success_count}/{total_count}")
                
                # Wait for next iteration
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Validator {self.validator_id} stopped by user")
        except Exception as e:
            print(f"❌ Validator error: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the validator"""
        self.running = False
        print(f"🛑 Stopping validator: {self.validator_id}")


# Template function for quick validator creation
def create_validator(
    validator_id: str = "template-validator",
    **kwargs
) -> AlphamindValidator:
    """Create a new Alphamind validator instance"""
    return AlphamindValidator(validator_id=validator_id, **kwargs)


# Example usage
async def main():
    """Example of using the validator template"""
    # Create validator instance
    validator = create_validator(
        validator_id="example-validator",
        top_n=20
    )
    
    # Run once
    print("🧪 Running single iteration...")
    results = await validator.run_once()
    print(f"Results: {json.dumps(results, indent=2)}")
    
    # Health check
    health = await validator.health_check()
    print(f"Health: {json.dumps(health, indent=2)}")
    
    # Uncomment to run continuously
    # await validator.run_continuous(interval=60)


if __name__ == "__main__":
    asyncio.run(main())
