#!/usr/bin/env python3
"""
Daily Emissions Collection Script
Fetches emissions data from Bittensor network and saves to GitHub
"""

import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path
sys.path.append(str(Path(__file__).parent))

from utils import GitHubManager, DiscordNotifier, ChecksumManager, load_config, setup_logging

def collect_emissions_data():
    """Collect emissions data using btcli"""
    print("🔍 Collecting emissions data from Bittensor network...")
    
    try:
        # Get subnet list
        result = subprocess.run(['btcli', 'subnet', 'list'], 
                              capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise Exception(f"btcli failed: {result.stderr}")
        
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

def save_emissions_data(emissions: dict, output_dir: Path) -> tuple:
    """Save emissions data to JSON and CSV files"""
    timestamp = datetime.now(timezone.utc)
    date_str = timestamp.strftime('%Y%m%d')
    
    # Prepare JSON data
    json_data = {
        'timestamp': timestamp.isoformat(),
        'date': date_str,
        'total_subnets': len(emissions),
        'emissions': emissions,
        'total_emission_rate': sum(emissions.values()),
        'avg_emission_rate': sum(emissions.values()) / len(emissions) if emissions else 0,
        'collection_method': 'btcli_subnet_list',
        'network': 'finney'
    }
    
    # Save JSON file
    json_file = output_dir / f'emissions_{date_str}.json'
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=2, sort_keys=True)
    
    # Save CSV file
    csv_file = output_dir / f'emissions_{date_str}.csv'
    with open(csv_file, 'w') as f:
        f.write('netuid,emission_rate,emission_percentage\n')
        for netuid, rate in sorted(emissions.items()):
            f.write(f'{netuid},{rate:.6f},{rate*100:.4f}\n')
    
    print(f"💾 Saved data to {json_file.name} and {csv_file.name}")
    return json_file, csv_file

def main():
    """Main emissions collection process"""
    print("🚀 TAO20 CPS - Daily Emissions Collection")
    print("=" * 50)
    
    # Setup
    setup_logging()
    config = load_config()
    
    # Add random jitter (0-5 minutes)
    jitter_seconds = random.randint(0, 300)
    print(f"🎲 Adding {jitter_seconds} second jitter (anti-manipulation)")
    time.sleep(jitter_seconds)
    
    print(f"🕐 Collection started at: {datetime.now(timezone.utc).isoformat()}")
    
    # Collect emissions data
    emissions = collect_emissions_data()
    if not emissions:
        print("❌ No emissions data collected")
        if config['discord_webhook']:
            notifier = DiscordNotifier(config['discord_webhook'])
            notifier.send_emissions_error("Failed to collect emissions data from btcli")
        sys.exit(1)
    
    # Save data
    emissions_dir = Path('emissions')
    emissions_dir.mkdir(exist_ok=True)
    
    json_file, csv_file = save_emissions_data(emissions, emissions_dir)
    
    # Calculate checksums
    checksum_manager = ChecksumManager()
    json_checksum = checksum_manager.calculate_sha256(json_file)
    csv_checksum = checksum_manager.calculate_sha256(csv_file)
    
    # Save checksums
    json_checksum_file = checksum_manager.save_checksum(json_file, json_checksum)
    csv_checksum_file = checksum_manager.save_checksum(csv_file, csv_checksum)
    
    print(f"🔐 SHA256 checksums calculated and saved")
    
    # Commit to GitHub
    if config['github_token']:
        github = GitHubManager(config['repo_path'], config['github_token'])
        github.setup_git_config()
        
        files_to_commit = [json_file, csv_file, json_checksum_file, csv_checksum_file]
        commit_message = f"Daily emissions collection - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        
        if github.add_and_commit(files_to_commit, commit_message):
            if github.push_to_github():
                print("✅ Data committed and pushed to GitHub")
                commit_hash = github.get_commit_hash()
                github_url = f"https://github.com/alexlange1/alphamind-transparency/commit/{commit_hash}"
            else:
                print("❌ Failed to push to GitHub")
                github_url = "Push failed"
        else:
            print("❌ Failed to commit to GitHub")
            github_url = "Commit failed"
    else:
        print("⚠️ No GitHub token configured - skipping commit")
        github_url = "No GitHub integration"
    
    # Send Discord notification
    if config['discord_webhook']:
        notifier = DiscordNotifier(config['discord_webhook'])
        notifier.send_emissions_success(
            filename=json_file.name,
            checksum=json_checksum,
            subnet_count=len(emissions)
        )
    
    # Show summary
    top_5 = sorted(emissions.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n📊 Top 5 subnets by emission rate:")
    for netuid, rate in top_5:
        print(f"  Subnet {netuid}: {rate:.6f} ({rate*100:.4f}%)")
    
    print(f"\n✅ Daily emissions collection completed successfully")
    print(f"📁 Files: {json_file.name}, {csv_file.name}")
    print(f"🔐 JSON SHA256: {json_checksum}")
    print(f"🌐 GitHub: {github_url}")

if __name__ == "__main__":
    main()
