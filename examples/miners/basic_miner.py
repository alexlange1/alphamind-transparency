#!/usr/bin/env python3
"""
Basic Alphamind Miner Example
Demonstrates how to create and run a simple miner
"""
import asyncio
from pathlib import Path

# Import the miner template
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from templates.miner_template import create_miner


async def main():
    """
    Basic miner example
    """
    print("🚀 Starting Basic Alphamind Miner Example")
    print("=" * 50)
    
    # Create a miner instance
    miner = create_miner(
        miner_id="basic-example-miner",
        interval=120,  # 2 minutes for demo
        out_dir=Path("./output")  # Local output directory
    )
    
    print(f"👤 Miner ID: {miner.miner_id}")
    print(f"📁 Output Directory: {miner.out_dir}")
    print(f"⏱️  Report Interval: {miner.interval}s")
    
    # Run a single iteration
    print("\n📊 Running single iteration...")
    results = await miner.run_once()
    print(f"✅ Iteration completed: {results}")
    
    # Show health status
    health = await miner.health_check()
    print(f"\n🏥 Health Check: {health}")
    
    # For continuous operation, uncomment the following:
    print("\n💡 To run continuously, uncomment the line below:")
    print("# await miner.run_continuous()")
    
    print("\n🎉 Basic miner example completed!")
    print("📚 Next: Try running 'python examples/validators/basic_validator.py'")


if __name__ == "__main__":
    asyncio.run(main())
