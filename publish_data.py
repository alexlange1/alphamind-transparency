#!/usr/bin/env python3
"""Simple AlphaMind Data Publisher"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VPS_HOST = "138.68.69.71"
VPS_DATA_PATH = "/opt/alphamind/data"

def pull_emissions_data():
    """Pull latest emissions data from VPS"""
    print("📥 Pulling emissions data from VPS...")
    
    try:
        # Create local data directory
        local_emissions_dir = Path("data/emissions")
        local_emissions_dir.mkdir(parents=True, exist_ok=True)
        
        # Pull latest emissions file
        result = subprocess.run([
            "scp", f"root@{VPS_HOST}:{VPS_DATA_PATH}/emissions_latest.json",
            str(local_emissions_dir / "emissions_latest.json")
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Failed to pull emissions data: {result.stderr}")
            return False
        
        # Rename with today's date
        today = datetime.now(timezone.utc).strftime('%Y%m%d')
        latest_file = local_emissions_dir / "emissions_latest.json"
        dated_file = local_emissions_dir / f"emissions_{today}.json"
        
        if latest_file.exists():
            latest_file.rename(dated_file)
            print(f"✅ Emissions data saved as {dated_file.name}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Failed to pull emissions data: {e}")
        return False

def pull_tao20_data():
    """Pull latest TAO20 data from VPS (if available)"""
    print("📥 Checking for TAO20 data on VPS...")
    
    try:
        # Create local data directory
        local_tao20_dir = Path("data/tao20")
        local_tao20_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if TAO20 data exists on VPS
        result = subprocess.run([
            "ssh", f"root@{VPS_HOST}", f"ls {VPS_DATA_PATH}/tao20_* 2>/dev/null | head -1"
        ], capture_output=True, text=True)
        
        if result.returncode != 0 or not result.stdout.strip():
            print("ℹ️ No TAO20 data found on VPS")
            return False
        
        # Pull the latest TAO20 file
        tao20_file = result.stdout.strip()
        local_tao20_file = local_tao20_dir / Path(tao20_file).name
        
        result = subprocess.run([
            "scp", f"root@{VPS_HOST}:{tao20_file}",
            str(local_tao20_file)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Failed to pull TAO20 data: {result.stderr}")
            return False
        
        print(f"✅ TAO20 data saved as {local_tao20_file.name}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to pull TAO20 data: {e}")
        return False

def commit_and_push():
    """Commit and push changes to GitHub"""
    print("📝 Committing and pushing changes...")
    
    try:
        # Add all changes
        subprocess.run(["git", "add", "."], check=True)
        
        # Check if there are changes to commit
        result = subprocess.run(["git", "diff", "--cached", "--exit-code"], capture_output=True)
        if result.returncode == 0:
            print("ℹ️ No changes to commit")
            return True
        
        # Commit with timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        commit_msg = f"Automated transparency update - {timestamp}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        # Push to main branch
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"✅ Successfully pushed changes: {commit_msg}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        return False

def main():
    """Main publishing process"""
    print(f"🚀 AlphaMind Data Publisher - {datetime.now(timezone.utc)}")
    
    # Pull data from VPS
    emissions_pulled = pull_emissions_data()
    tao20_pulled = pull_tao20_data()
    
    if not emissions_pulled and not tao20_pulled:
        print("❌ No data pulled from VPS")
        sys.exit(1)
    
    # Commit and push changes
    if commit_and_push():
        print("✅ Publishing completed successfully")
    else:
        print("❌ Publishing failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
