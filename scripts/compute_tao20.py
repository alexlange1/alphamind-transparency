#!/usr/bin/env python3
"""
TAO20 Bi-weekly Rebalancing Script
Computes TAO20 index from last 14 days of emissions data
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# Add scripts directory to path
sys.path.append(str(Path(__file__).parent))

from utils import GitHubManager, DiscordNotifier, ChecksumManager, load_config, setup_logging

def load_emissions_data(days: int = 14) -> List[Dict]:
    """Load emissions data from the last N days"""
    print(f"📊 Loading emissions data from last {days} days...")
    
    emissions_dir = Path('emissions')
    if not emissions_dir.exists():
        raise Exception("Emissions directory not found")
    
    # Get all emissions JSON files
    emissions_files = list(emissions_dir.glob('emissions_*.json'))
    if not emissions_files:
        raise Exception("No emissions files found")
    
    # Sort by date and take the last N files
    emissions_files.sort()
    recent_files = emissions_files[-days:]
    
    print(f"📁 Found {len(recent_files)} emissions files")
    
    emissions_data = []
    for file_path in recent_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                emissions_data.append(data)
                print(f"  ✅ Loaded: {file_path.name}")
        except Exception as e:
            print(f"  ❌ Failed to load {file_path.name}: {e}")
    
    if not emissions_data:
        raise Exception("No valid emissions data loaded")
    
    return emissions_data

def compute_average_emissions(emissions_data: List[Dict]) -> Dict[int, float]:
    """Compute 14-day average emissions for each subnet"""
    print("🧮 Computing 14-day average emissions...")
    
    # Collect all subnets across all days
    all_subnets = set()
    for data in emissions_data:
        all_subnets.update(data['emissions'].keys())
    
    # Convert string keys to integers
    all_subnets = {int(netuid) for netuid in all_subnets}
    
    # Calculate averages
    subnet_averages = {}
    for netuid in all_subnets:
        netuid_str = str(netuid)
        rates = []
        
        for data in emissions_data:
            if netuid_str in data['emissions']:
                rates.append(data['emissions'][netuid_str])
        
        if rates:
            subnet_averages[netuid] = sum(rates) / len(rates)
    
    print(f"📈 Computed averages for {len(subnet_averages)} subnets")
    return subnet_averages

def select_top_20_subnets(subnet_averages: Dict[int, float]) -> List[Tuple[int, float]]:
    """Select top 20 subnets by average emissions"""
    print("🏆 Selecting top 20 subnets...")
    
    # Sort by emission rate (descending)
    sorted_subnets = sorted(subnet_averages.items(), key=lambda x: x[1], reverse=True)
    
    # Take top 20
    top_20 = sorted_subnets[:20]
    
    print(f"✅ Selected top 20 subnets")
    return top_20

def normalize_weights(top_20: List[Tuple[int, float]]) -> List[Dict]:
    """Normalize weights so they sum to 1.0 (100%)"""
    print("⚖️ Normalizing weights...")
    
    # Extract just the emission rates
    rates = [rate for _, rate in top_20]
    total_rate = sum(rates)
    
    # Normalize to sum to 1.0
    normalized_weights = [rate / total_rate for rate in rates]
    
    # Create result list with rank, netuid, weight, and percentage
    result = []
    for i, ((netuid, _), weight) in enumerate(zip(top_20, normalized_weights), 1):
        result.append({
            'rank': i,
            'netuid': netuid,
            'weight': weight,
            'weight_percentage': weight * 100,
            'avg_emission_rate': top_20[i-1][1]
        })
    
    print(f"✅ Weights normalized (total: {sum(normalized_weights):.6f})")
    return result

def save_tao20_data(tao20_data: List[Dict], output_dir: Path) -> Path:
    """Save TAO20 data to JSON file only"""
    timestamp = datetime.now(timezone.utc)
    date_str = timestamp.strftime('%Y%m%d')
    
    # Prepare JSON data
    json_data = {
        'metadata': {
            'index_name': 'TAO20',
            'index_type': 'Top-20 Emissions-Weighted Bittensor Subnet Index',
            'rebalance_date': date_str,
            'generation_timestamp': timestamp.isoformat(),
            'methodology': '14-day average emissions, top 20 subnets, normalized weights',
            'total_constituents': len(tao20_data),
            'data_period_days': 14,
            'operating_mode': 'PRODUCTION'
        },
        'tao20_constituents': tao20_data
    }
    
    # Save JSON file only
    json_file = output_dir / f'tao20_{date_str}.json'
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=2, sort_keys=True)
    
    print(f"💾 Saved TAO20 data to {json_file.name}")
    return json_file

def should_rebalance() -> Tuple[bool, str]:
    """Check if it's time for bi-weekly rebalancing (every 2nd Sunday)"""
    now = datetime.now(timezone.utc)
    
    # Check if it's Sunday
    if now.weekday() != 6:  # Sunday is 6
        return False, f"Not Sunday (today is {now.strftime('%A')})"
    
    # Check if it's the 2nd Sunday of the month
    # Simple heuristic: if day of month is 8-14, it's likely the 2nd Sunday
    if 8 <= now.day <= 14:
        return True, f"2nd Sunday of month (day {now.day})"
    
    return False, f"Not 2nd Sunday (day {now.day})"

def main():
    """Main TAO20 rebalancing process"""
    print("🎯 TAO20 CPS - Bi-weekly Rebalancing")
    print("=" * 45)
    
    # Setup
    setup_logging()
    config = load_config()
    
    # Check if rebalancing is due
    should_reb, reason = should_rebalance()
    print(f"📅 Rebalancing check: {reason}")
    
    if not should_reb:
        print("⏳ TAO20 rebalancing not due yet")
        sys.exit(0)
    
    print("🎯 TAO20 rebalancing is due - proceeding...")
    
    try:
        # Load emissions data
        emissions_data = load_emissions_data(14)
        
        # Compute averages
        subnet_averages = compute_average_emissions(emissions_data)
        
        # Select top 20
        top_20 = select_top_20_subnets(subnet_averages)
        
        # Normalize weights
        tao20_data = normalize_weights(top_20)
        
        # Save data
        tao20_dir = Path('tao20')
        tao20_dir.mkdir(exist_ok=True)
        
        json_file = save_tao20_data(tao20_data, tao20_dir)
        
        # Commit to GitHub
        github_url = "No GitHub integration"
        if config['github_token']:
            github = GitHubManager(config['repo_path'], config['github_token'])
            github.setup_git_config()
            
            files_to_commit = [json_file]
            commit_message = f"TAO20 rebalancing - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            
            if github.add_and_commit(files_to_commit, commit_message):
                if github.push_to_github():
                    print("✅ TAO20 data committed and pushed to GitHub")
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
        
        # Send Discord notification
        if config['discord_webhook']:
            notifier = DiscordNotifier(config['discord_webhook'])
            notifier.send_tao20_success(
                date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                top_3=tao20_data[:3],
                checksum="N/A",
                github_url=github_url
            )
        
        # Show summary
        print("\n🏆 TAO20 Index Composition:")
        for item in tao20_data[:10]:  # Show top 10
            print(f"  {item['rank']:2d}. Subnet {item['netuid']:3d}: {item['weight_percentage']:6.2f}%")
        
        print(f"\n✅ TAO20 rebalancing completed successfully")
        print(f"📁 File: {json_file.name}")
        print(f"🌐 GitHub: {github_url}")
        
    except Exception as e:
        print(f"❌ TAO20 rebalancing failed: {e}")
        if config['discord_webhook']:
            notifier = DiscordNotifier(config['discord_webhook'])
            notifier.send_tao20_error(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
