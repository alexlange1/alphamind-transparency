#!/usr/bin/env python3
"""
TAO20 Bi-Weekly Index Publisher
- Publishes every 14 days (aligned with Bittensor epochs)
- Full transparency via S3 and GitHub
- Public index composition updates
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import sys

class TAO20Publisher:
    def __init__(self):
        self.data_dir = Path('out')
        self.rebalance_interval = 14  # days
        
    def should_publish_index(self):
        """Check if it's time for bi-weekly index publication"""
        
        last_publication_file = self.data_dir / 'last_tao20_publication.json'
        
        if last_publication_file.exists():
            with open(last_publication_file) as f:
                last_pub = json.load(f)
                last_date = datetime.fromisoformat(last_pub['timestamp'])
                days_since = (datetime.now() - last_date).days
                
                print(f'📅 Days since last TAO20 publication: {days_since}')
                
                if days_since >= self.rebalance_interval:
                    return True, f'{days_since} days since last publication (≥14 day cycle)'
                else:
                    return False, f'Only {days_since} days since last publication (need 14)'
        else:
            return True, 'No previous TAO20 publication found - first publication'
    
    def create_tao20_index(self):
        """Generate the TAO20 index using the production system"""
        
        print('🏗️ Generating TAO20 index...')
        
        # Run the production system
        result = subprocess.run([
            '/opt/alphamind/venv/bin/python3',
            'scripts/tao20_production_system.py'
        ], cwd='/opt/alphamind/src', capture_output=True, text=True)
        
        if result.returncode == 0:
            print('✅ TAO20 index generated successfully')
            
            # Load the generated index
            index_file = self.data_dir / 'tao20_index_latest.json'
            if index_file.exists():
                with open(index_file) as f:
                    return json.load(f)
            else:
                print('❌ Index file not found after generation')
                return None
        else:
            print(f'❌ Failed to generate TAO20 index: {result.stderr}')
            return None
    
    def create_publication_package(self, index_data):
        """Create complete publication package for transparency"""
        
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y%m%d')
        
        # Create publication directory
        pub_dir = self.data_dir / f'tao20_publication_{date_str}'
        pub_dir.mkdir(exist_ok=True)
        
        publication_package = {
            'publication_info': {
                'publication_date': timestamp.isoformat(),
                'index_name': 'TAO20',
                'index_type': 'Top-20 Concentrated Bittensor Subnet Index',
                'publication_frequency': 'Bi-weekly (14 days)',
                'data_source': 'AlphaMind Transparent Emissions Collection',
                'methodology': 'Emissions-weighted with strict eligibility requirements'
            },
            'index_composition': index_data,
            'transparency_verification': {
                'daily_emissions_data': 'https://alphamind-emissions-data.s3.amazonaws.com/emissions/',
                'verification_instructions': 'All emissions data can be independently verified via S3 bucket',
                'github_transparency_repo': 'Coming soon - public verification repository',
                'methodology_documentation': 'Detailed methodology available in publication package'
            },
            'regulatory_disclosures': {
                'disclaimer': 'This index is for informational purposes only and does not constitute investment advice',
                'methodology_changes': 'Any methodology changes will be announced with 30-day notice',
                'data_quality': 'All data is cryptographically signed and publicly verifiable',
                'operating_mode': index_data['metadata'].get('operating_mode', 'PRODUCTION')
            }
        }
        
        # Save complete publication package
        package_file = pub_dir / 'tao20_complete_publication.json'
        with open(package_file, 'w') as f:
            json.dump(publication_package, f, indent=2)
        
        # Create human-readable summary
        summary_file = pub_dir / 'tao20_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(self.create_readable_summary(publication_package))
        
        # Create CSV for easy consumption
        csv_file = pub_dir / 'tao20_weights.csv'
        self.create_csv_export(index_data, csv_file)
        
        print(f'📦 Publication package created: {pub_dir}')
        
        return pub_dir, publication_package
    
    def create_readable_summary(self, publication_package):
        """Create human-readable summary"""
        
        summary = f"""
TAO20 INDEX PUBLICATION
======================
Date: {publication_package['publication_info']['publication_date']}
Type: {publication_package['publication_info']['index_type']}
Frequency: {publication_package['publication_info']['publication_frequency']}

INDEX COMPOSITION (Top 10):
"""
        
        index_data = publication_package['index_composition']
        constituents_key = 'tao20_constituents' if 'tao20_constituents' in index_data else 'collection_phase_constituents'
        
        summary += 'Rank | Subnet | Weight\n'
        summary += '-----|--------|-------\n'
        
        for holding in index_data.get(constituents_key, [])[:10]:
            summary += f'{holding["rank"]:4d} | {holding["netuid"]:6d} | {holding["weight_percentage"]:6.2f}%\n'
        
        summary += f"""
OPERATING MODE: {index_data['metadata'].get('operating_mode', 'PRODUCTION')}

TRANSPARENCY:
- All daily emissions data: {publication_package['transparency_verification']['daily_emissions_data']}
- Cryptographically signed and publicly verifiable
- Independent verification instructions included

DISCLAIMER: {publication_package['regulatory_disclosures']['disclaimer']}
"""
        
        return summary
    
    def create_csv_export(self, index_data, csv_file):
        """Create CSV export of index weights"""
        
        constituents_key = 'tao20_constituents' if 'tao20_constituents' in index_data else 'collection_phase_constituents'
        constituents = index_data.get(constituents_key, [])
        
        with open(csv_file, 'w') as f:
            f.write('rank,netuid,weight_percentage,weight_decimal\n')
            for holding in constituents:
                f.write(f'{holding["rank"]},{holding["netuid"]},{holding["weight_percentage"]},{holding["weight"]}\n')
    
    def upload_to_s3(self, pub_dir):
        """Upload publication to S3 for transparency"""
        
        print('☁️ Uploading TAO20 publication to S3...')
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        s3_path = f's3://alphamind-emissions-data/tao20_publications/{date_str}/'
        
        try:
            # Upload publication directory to S3
            result = subprocess.run([
                'aws', 's3', 'sync', str(pub_dir), s3_path,
                '--exclude', '*.pyc'
            ], check=True, capture_output=True, text=True)
            
            print(f'✅ TAO20 publication uploaded to: {s3_path}')
            
            # Also update latest
            latest_s3_path = 's3://alphamind-emissions-data/tao20_publications/latest/'
            subprocess.run([
                'aws', 's3', 'sync', str(pub_dir), latest_s3_path,
                '--exclude', '*.pyc'
            ], check=True)
            
            return s3_path
            
        except subprocess.CalledProcessError as e:
            print(f'❌ S3 upload failed: {e.stderr}')
            return None
    
    def record_publication(self, index_data, s3_path):
        """Record successful publication"""
        
        publication_record = {
            'timestamp': datetime.now().isoformat(),
            'index_metadata': index_data['metadata'],
            's3_publication_url': s3_path,
            'next_publication_due': (datetime.now() + timedelta(days=self.rebalance_interval)).isoformat(),
            'constituents_count': len(index_data.get('tao20_weights', {})),
            'operating_mode': index_data['metadata'].get('operating_mode', 'PRODUCTION')
        }
        
        with open(self.data_dir / 'last_tao20_publication.json', 'w') as f:
            json.dump(publication_record, f, indent=2)
        
        print(f'📝 Publication recorded - next due: {publication_record["next_publication_due"]}')
    
    def publish_tao20_index(self):
        """Main publication function"""
        
        print('🚀 TAO20 Bi-Weekly Index Publication Process')
        print('=' * 50)
        
        # Check if publication is due
        should_publish, reason = self.should_publish_index()
        
        print(f'📅 Publication check: {reason}')
        
        if not should_publish:
            print('⏳ TAO20 publication not due yet')
            return False
        
        print('🎯 TAO20 publication is due - proceeding...')
        
        # Generate the index
        index_data = self.create_tao20_index()
        if not index_data:
            print('❌ Failed to generate TAO20 index')
            return False
        
        # Create publication package
        pub_dir, publication_package = self.create_publication_package(index_data)
        
        # Upload to S3 for transparency
        s3_path = self.upload_to_s3(pub_dir)
        
        if s3_path:
            # Record successful publication
            self.record_publication(index_data, s3_path)
            
            print('\n' + '=' * 60)
            print('🎉 TAO20 INDEX PUBLISHED SUCCESSFULLY!')
            print('=' * 60)
            print(f'📅 Publication Date: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}')
            print(f'🌐 Public URL: {s3_path}')
            print(f'📊 Constituents: {len(index_data.get("tao20_weights", {}))}')
            print(f'🎯 Mode: {index_data["metadata"].get("operating_mode", "PRODUCTION")}')
            print(f'📅 Next Publication: {(datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")}')
            
            return True
        else:
            print('❌ Publication failed due to S3 upload error')
            return False

def main():
    os.chdir('/opt/alphamind/src')
    
    publisher = TAO20Publisher()
    
    try:
        return publisher.publish_tao20_index()
    except Exception as e:
        print(f'❌ Publication error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
