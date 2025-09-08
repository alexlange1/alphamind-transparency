#!/usr/bin/env python3
"""
TAO20 Production System
Generates TAO20 index from emissions data using the production algorithm
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
import os

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tao20.validator import compute_index_weights_from_reports
from tao20.models import EmissionsReport


class TAO20ProductionSystem:
    def __init__(self):
        self.data_dir = Path('out')
        self.data_dir.mkdir(exist_ok=True)
        
    def load_latest_emissions(self):
        """Load the latest emissions data"""
        
        # Try to load from the latest emissions file
        latest_emissions_file = self.data_dir / 'emissions_latest.json'
        if not latest_emissions_file.exists():
            # Fallback to daily emissions
            import glob
            daily_files = glob.glob(str(self.data_dir / 'emissions_daily_*.json'))
            if daily_files:
                latest_emissions_file = Path(max(daily_files))
            else:
                raise FileNotFoundError("No emissions data found")
        
        print(f'📊 Loading emissions data from: {latest_emissions_file}')
        
        with open(latest_emissions_file) as f:
            emissions_data = json.load(f)
        
        # Convert to EmissionsReport format
        emissions_by_netuid = {}
        raw_emissions = emissions_data.get('emissions_by_netuid', {})
        
        for netuid_str, emission_value in raw_emissions.items():
            netuid = int(netuid_str)
            emissions_by_netuid[netuid] = float(emission_value)
        
        print(f'✅ Loaded emissions for {len(emissions_by_netuid)} subnets')
        
        # Create EmissionsReport
        report = EmissionsReport(
            snapshot_ts=datetime.now(timezone.utc).isoformat(),
            emissions_by_netuid=emissions_by_netuid,
            miner_id="alphamind_production",
            stake_tao=0.0,
            signature="",
            signer_ss58="",
            schema_version="1.0.0"
        )
        
        return [report]
    
    def generate_tao20_index(self):
        """Generate the TAO20 index from emissions data"""
        
        print('🏗️ TAO20 Production System - Generating Index')
        print('=' * 50)
        
        try:
            # Load emissions data
            reports = self.load_latest_emissions()
            
            # Compute index weights (top 20 subnets)
            print('🔢 Computing TAO20 index weights...')
            index_weights = compute_index_weights_from_reports(reports, top_n=20)
            
            if not index_weights:
                raise ValueError("No index weights computed")
            
            print(f'✅ Generated weights for {len(index_weights)} constituents')
            
            # Sort by weight (descending)
            sorted_constituents = sorted(index_weights.items(), key=lambda x: x[1], reverse=True)
            
            # Create index data structure
            timestamp = datetime.now(timezone.utc)
            
            index_data = {
                'metadata': {
                    'index_name': 'TAO20',
                    'index_type': 'Top-20 Concentrated Bittensor Subnet Index',
                    'generation_timestamp': timestamp.isoformat(),
                    'generation_date': timestamp.strftime('%Y-%m-%d'),
                    'operating_mode': 'PRODUCTION',
                    'data_source': 'AlphaMind Emissions Collection',
                    'methodology': 'Emissions-weighted top 20 subnets',
                    'rebalance_frequency': 'Bi-weekly (every 14 days)',
                    'schema_version': '1.0.0'
                },
                'tao20_constituents': [
                    {
                        'netuid': netuid,
                        'weight': weight,
                        'weight_percentage': weight * 100,
                        'rank': rank + 1
                    }
                    for rank, (netuid, weight) in enumerate(sorted_constituents)
                ],
                'index_statistics': {
                    'total_constituents': len(index_weights),
                    'total_weight': sum(index_weights.values()),
                    'top_5_weight': sum(weight for _, weight in sorted_constituents[:5]),
                    'concentration_ratio': sum(weight for _, weight in sorted_constituents[:5]) / sum(index_weights.values()) if index_weights else 0
                },
                'generation_info': {
                    'emissions_reports_count': len(reports),
                    'total_subnets_evaluated': len(reports[0].emissions_by_netuid) if reports else 0,
                    'selection_method': 'top_20_by_emissions',
                    'weight_normalization': 'sum_to_one'
                }
            }
            
            # Save to output files
            latest_file = self.data_dir / 'tao20_index_latest.json'
            timestamped_file = self.data_dir / f'tao20_index_{timestamp.strftime("%Y%m%d_%H%M%S")}.json'
            
            for output_file in [latest_file, timestamped_file]:
                with open(output_file, 'w') as f:
                    json.dump(index_data, f, indent=2)
                print(f'💾 Saved: {output_file}')
            
            # Print summary
            print('\n' + '=' * 60)
            print('🎉 TAO20 INDEX GENERATED SUCCESSFULLY')
            print('=' * 60)
            print(f'📊 Constituents: {len(index_weights)}')
            print(f'🎯 Top 5 Concentration: {index_data["index_statistics"]["concentration_ratio"]:.1%}')
            print(f'📅 Generation Time: {timestamp.strftime("%Y-%m-%d %H:%M UTC")}')
            print('\n📈 Top 10 Constituents:')
            
            for i, (netuid, weight) in enumerate(sorted_constituents[:10], 1):
                print(f'  {i:2d}. Subnet {netuid:3d}: {weight:.4f} ({weight*100:.2f}%)')
            
            print('=' * 60)
            
            return True
            
        except Exception as e:
            print(f'❌ Failed to generate TAO20 index: {e}')
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point"""
    
    # Change to project directory
    os.chdir('/opt/alphamind/src')
    
    # Create and run production system
    system = TAO20ProductionSystem()
    success = system.generate_tao20_index()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
