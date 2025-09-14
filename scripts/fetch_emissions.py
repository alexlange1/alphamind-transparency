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
    """Collect real emissions data using btcli JSON output"""
    print("🔍 Collecting real emissions data from Bittensor network...")
    
    try:
        # Get subnet list with JSON output for reliable parsing
        result = subprocess.run(['btcli', 'subnet', 'list', '--network', 'finney', '--json-output'], 
                              capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise Exception(f"btcli failed: {result.stderr}")
        
        # Parse JSON output
        data = json.loads(result.stdout)
        subnets = data.get('subnets', {})
        
        emissions = {}
        total_emission = 0
        
        for netuid_str, subnet_data in subnets.items():
            try:
                netuid = int(netuid_str)
                emission = subnet_data.get('emission', 0.0)
                # Exclude subnet 0 (root network) and only include subnets with actual emissions
                if netuid != 0 and emission > 0:
                    emissions[netuid] = emission
                    total_emission += emission
            except (ValueError, TypeError):
                continue
        
        print(f"✅ Collected real emissions from {len(emissions)} active subnets")
        print(f"📊 Total emission rate: {total_emission:.6f}")
        return emissions, data
        
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        return None, None

def save_emissions_data(emissions: dict, raw_data: dict, output_dir: Path) -> tuple:
    """Save real emissions data to JSON and CSV files"""
    timestamp = datetime.now(timezone.utc)
    date_str = timestamp.strftime('%Y%m%d')
    
    # Prepare JSON data with real Bittensor information
    json_data = {
        'metadata': {
            'timestamp': timestamp.isoformat(),
            'date': date_str,
            'source': 'bittensor_finney_network',
            'collection_method': 'btcli_subnet_list_json',
            'network': 'finney',
            'total_active_subnets': len(emissions),
            'total_subnets_on_network': raw_data.get('total_netuids', 0),
            'total_tao_emitted': raw_data.get('total_tao_emitted', 0),
            'total_emission_rate': raw_data.get('total_emissions', 0),
            'emission_percentage': raw_data.get('emission_percentage', 0)
        },
        'emissions': emissions,
        'statistics': {
            'total_emission_rate': sum(emissions.values()),
            'avg_emission_rate': sum(emissions.values()) / len(emissions) if emissions else 0,
            'max_emission_rate': max(emissions.values()) if emissions else 0,
            'min_emission_rate': min(emissions.values()) if emissions else 0,
            'active_subnets': len(emissions)
        }
    }
    
    # Save JSON file
    json_file = output_dir / f'emissions_{date_str}.json'
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=2, sort_keys=True)
    
    # Save CSV file
    csv_file = output_dir / f'emissions_{date_str}.csv'
    with open(csv_file, 'w') as f:
        f.write('netuid,emission_rate,emission_percentage,rank\n')
        # Sort by emission rate descending
        sorted_emissions = sorted(emissions.items(), key=lambda x: x[1], reverse=True)
        for rank, (netuid, rate) in enumerate(sorted_emissions, 1):
            percentage = (rate / sum(emissions.values())) * 100 if sum(emissions.values()) > 0 else 0
            f.write(f'{netuid},{rate:.6f},{percentage:.4f},{rank}\n')
    
    print(f"💾 Saved real data to {json_file.name} and {csv_file.name}")
    return json_file, csv_file

def main():
    """Main emissions collection process"""
    print("🚀 TAO20 CPS - Real Daily Emissions Collection")
    print("=" * 55)
    
    # Setup
    setup_logging()
    config = load_config()
    
    # Add random jitter (0-5 minutes)
    jitter_seconds = random.randint(0, 300)
    print(f"🎲 Adding {jitter_seconds} second jitter (anti-manipulation)")
    time.sleep(jitter_seconds)
    
    print(f"🕐 Collection started at: {datetime.now(timezone.utc).isoformat()}")
    
    # Collect real emissions data
    emissions, raw_data = collect_emissions_data()
    if not emissions:
        print("❌ No emissions data collected")
        if config['discord_webhook']:
            notifier = DiscordNotifier(config['discord_webhook'])
            notifier.send_emissions_error("Failed to collect real emissions data from btcli")
        sys.exit(1)
    
    # Save data
    emissions_dir = Path('emissions')
    emissions_dir.mkdir(exist_ok=True)
    
    json_file, csv_file = save_emissions_data(emissions, raw_data, emissions_dir)
    
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
        commit_message = f"Real daily emissions collection - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        
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
    
    # Show summary with real data
    top_10 = sorted(emissions.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\n📊 Top 10 subnets by real emission rate:")
    total_emissions = sum(emissions.values())
    for rank, (netuid, rate) in enumerate(top_10, 1):
        percentage = (rate / total_emissions) * 100
        print(f"  {rank:2d}. Subnet {netuid:3d}: {rate:.6f} ({percentage:.2f}%)")
    
    print(f"\n✅ Real daily emissions collection completed successfully")
    print(f"📁 Files: {json_file.name}, {csv_file.name}")
    print(f"🔐 JSON SHA256: {json_checksum}")
    print(f"🌐 GitHub: {github_url}")
    print(f"🎯 Total active subnets: {len(emissions)}")
    print(f"📈 Total emission rate: {total_emissions:.6f}")

if __name__ == "__main__":
    main()
