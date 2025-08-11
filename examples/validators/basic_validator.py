#!/usr/bin/env python3
"""
Basic Alphamind Validator Example
Demonstrates how to create and run a simple validator
"""
import asyncio
import json
from pathlib import Path

# Import the validator template
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from templates.validator_template import create_validator


async def main():
    """
    Basic validator example
    """
    print("🚀 Starting Basic Alphamind Validator Example")
    print("=" * 50)
    
    # Create a validator instance
    validator = create_validator(
        validator_id="basic-example-validator",
        in_dir=Path("./input"),   # Input directory for miner reports
        out_dir=Path("./output"), # Output directory for aggregated data
        top_n=20                  # Top 20 subnets
    )
    
    print(f"👤 Validator ID: {validator.validator_id}")
    print(f"📥 Input Directory: {validator.in_dir}")
    print(f"📤 Output Directory: {validator.out_dir}")
    print(f"🏆 Top N Subnets: {validator.top_n}")
    
    # Run a single iteration
    print("\n📊 Running single iteration...")
    results = await validator.run_once()
    
    # Display results nicely
    print("\n✅ Iteration completed:")
    for task, result in results.items():
        status = "✅" if result.get("success", False) else "❌"
        print(f"  {status} {task.title()}: {result.get('error', 'Success')}")
        
        # Show additional details for successful operations
        if result.get("success"):
            if task == "aggregation" and "weights_count" in result:
                print(f"    └─ Processed {result['weights_count']} subnet weights")
            elif task == "vault_update" and "nav" in result:
                print(f"    └─ NAV: {result['nav']:.6f} TAO")
    
    # Show health status
    health = await validator.health_check()
    print(f"\n🏥 Health Check:")
    print(f"  Status: {health['status']}")
    print(f"  Weights: {health['weights_count']} subnets")
    print(f"  Last Aggregation: {health['last_aggregation'] or 'Never'}")
    
    # Show generated files
    print(f"\n📄 Generated Files:")
    output_dir = Path(validator.out_dir)
    for file_path in output_dir.glob("*.json"):
        size_kb = file_path.stat().st_size / 1024
        print(f"  📄 {file_path.name} ({size_kb:.1f} KB)")
    
    # For continuous operation, uncomment the following:
    print("\n💡 To run continuously, uncomment the line below:")
    print("# await validator.run_continuous(interval=300)")
    
    print("\n🎉 Basic validator example completed!")
    print("📚 Next: Try running './alphamind validator serve' to start the API")


if __name__ == "__main__":
    asyncio.run(main())
