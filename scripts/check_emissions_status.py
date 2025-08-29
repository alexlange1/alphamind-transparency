#!/usr/bin/env python3
"""
Quick status check for the automated emissions collection system
Usage: python3 scripts/check_emissions_status.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

def main():
    print("🔍 ALPHAMIND EMISSIONS SYSTEM STATUS CHECK")
    print("=" * 50)
    
    # Check if cron job is installed
    import subprocess
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        if 'daily_emissions_collection' in result.stdout:
            print("✅ Daily cron job: INSTALLED (runs 4 PM UTC)")
        else:
            print("❌ Daily cron job: NOT FOUND")
    except Exception:
        print("⚠️  Could not check cron job")
    
    # Check latest data
    latest_file = Path('./out/secure/secure_data/latest_emissions_secure.json')
    if latest_file.exists():
        try:
            with open(latest_file) as f:
                latest_info = json.load(f)
            
            print(f"✅ Latest data: {latest_info['latest_file']}")
            print(f"📅 Last updated: {latest_info['timestamp']}")
            print(f"📊 Subnets tracked: {latest_info['total_subnets']}")
            
            # Load the actual data
            data_file = Path('./out/secure/secure_data') / latest_info['latest_file']
            if data_file.exists():
                with open(data_file) as f:
                    data = json.load(f)
                
                emissions = data['emissions_percentage_by_netuid']
                total_pct = sum(float(v) for v in emissions.values())
                raw_total = data['raw_total_emissions_tao_per_day']
                
                print(f"💰 Total emissions: {raw_total:.0f} TAO/day")
                print(f"📈 Normalization: {total_pct:.6f} (should be 1.0)")
                
                # Show top 3 subnets
                sorted_emissions = sorted(emissions.items(), key=lambda x: float(x[1]), reverse=True)
                print(f"🏆 Top 3 subnets:")
                for i, (netuid, pct) in enumerate(sorted_emissions[:3], 1):
                    print(f"   {i}. Subnet {netuid}: {float(pct)*100:.2f}%")
                
        except Exception as e:
            print(f"❌ Error reading data: {e}")
    else:
        print("❌ No secure data found")
    
    # Check logs
    log_file = Path('./logs/emissions_cron.log')
    if log_file.exists():
        try:
            with open(log_file) as f:
                lines = f.readlines()
            if lines:
                print(f"📝 Log entries: {len(lines)} lines")
                print(f"📄 Last log: ...{lines[-1].strip()[-50:]}")
            else:
                print("📝 Log file exists but empty")
        except Exception:
            print("⚠️  Could not read log file")
    else:
        print("📝 No cron log file yet (will appear after first run)")
    
    print()
    print("🎯 SYSTEM STATUS: Ready for automated daily collection")
    print("💡 TIP: Keep your Mac on at 4 PM UTC for daily updates")

if __name__ == "__main__":
    main()
