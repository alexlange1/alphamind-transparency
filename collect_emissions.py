#!/usr/bin/env python3
"""Simple AlphaMind Emissions Collector"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

def collect_emissions():
    """Collect emissions data using btcli"""
    print("🔍 Collecting emissions data...")
    
    try:
        # Get subnet list
        result = subprocess.run(['btcli', 'subnet', 'list'], 
                              capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"❌ btcli failed: {result.stderr}")
            return None
        
        # Parse subnet data - look for lines that start with numbers
        lines = result.stdout.strip().split('\n')
        emissions = {}
        
        for line in lines:
            # Skip empty lines and header lines
            if not line.strip() or not line.strip()[0].isdigit():
                continue
                
            # Split by whitespace and filter out empty strings
            parts = [p for p in line.split() if p]
            
            if len(parts) >= 4:
                try:
                    netuid = int(parts[0])
                    # Look for emission rate - it's usually a decimal number
                    emission_rate = None
                    for part in parts[1:]:
                        try:
                            # Try to parse as decimal
                            val = float(part)
                            if 0 <= val <= 1:  # Reasonable emission rate range
                                emission_rate = val
                                break
                        except ValueError:
                            continue
                    
                    if emission_rate is not None:
                        emissions[netuid] = emission_rate
                except (ValueError, IndexError):
                    continue
        
        print(f"✅ Collected emissions from {len(emissions)} subnets")
        return emissions
        
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        return None

def save_data(emissions):
    """Save emissions data to JSON file"""
    timestamp = datetime.now(timezone.utc)
    date_str = timestamp.strftime('%Y%m%d')
    
    data = {
        'timestamp': timestamp.isoformat(),
        'date': date_str,
        'total_subnets': len(emissions),
        'emissions': emissions,
        'total_emission_rate': sum(emissions.values()),
        'avg_emission_rate': sum(emissions.values()) / len(emissions) if emissions else 0
    }
    
    # Save to file
    output_dir = Path('/opt/alphamind/data')
    output_dir.mkdir(exist_ok=True)
    
    filename = f'emissions_{date_str}.json'
    filepath = output_dir / filename
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)
    
    # Also save as latest
    latest_file = output_dir / 'emissions_latest.json'
    with open(latest_file, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)
    
    print(f"💾 Saved data to {filepath}")
    return filepath

def main():
    """Main collection process"""
    print(f"🚀 AlphaMind Emissions Collection - {datetime.now(timezone.utc)}")
    
    # Collect emissions
    emissions = collect_emissions()
    if not emissions:
        print("❌ No emissions data collected")
        sys.exit(1)
    
    # Save data
    filepath = save_data(emissions)
    
    # Show summary
    top_5 = sorted(emissions.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n📊 Top 5 subnets by emission rate:")
    for netuid, rate in top_5:
        print(f"  Subnet {netuid}: {rate:.6f} ({rate*100:.4f}%)")
    
    print(f"\n✅ Collection completed successfully")

if __name__ == "__main__":
    main()
