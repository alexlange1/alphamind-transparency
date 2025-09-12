#!/usr/bin/env python3
"""
TAO20 Sunday Bi-Weekly Publisher
- Publishes every 2 weeks on Sunday at 16:05 UTC
- 5 minutes after emissions collection completes
- Perfect timing for weekend portfolio updates
"""

import json
import os
import subprocess
from pathlib import Path
import sys

class TAO20SundayPublisher:
    def __init__(self):
        self.data_dir = Path('out')
        self.rebalance_interval = 14  # days
        self.publication_day = 6  # Sunday (0=Monday, 6=Sunday)
        
    def get_constituents_key(self, index_data):
        """Get the correct key for constituents data"""
        return 'tao20_constituents' if 'tao20_constituents' in index_data else 'collection_phase_constituents'
    
    def get_constituents_count(self, index_data):
        """Get the correct count of constituents"""
        constituents_key = self.get_constituents_key(index_data)
        constituents = index_data.get(constituents_key, [])
        return len(constituents)
        
    def is_sunday(self):
        """Check if today is Sunday"""
        return datetime.now(timezone.utc).weekday() == self.publication_day
    
    def get_last_sunday(self):
        """Get the most recent Sunday date"""
        today = datetime.now(timezone.utc)
        days_since_sunday = (today.weekday() + 1) % 7
        last_sunday = today - timedelta(days=days_since_sunday)
        return last_sunday.replace(hour=16, minute=5, second=0, microsecond=0)
    
    def should_publish_index(self):
        """Check if it's time for bi-weekly Sunday publication"""
        
        # Only publish on Sundays
        if not self.is_sunday():
            return False, f'Today is {datetime.now(timezone.utc).strftime("%A")} - only publish on Sundays'
        
        # Check if it's after 16:05 UTC
        now = datetime.now(timezone.utc)
        if now.hour < 16 or (now.hour == 16 and now.minute < 5):
            return False, f'Too early - wait until 16:05 UTC (currently {now.strftime("%H:%M")} UTC)'
        
        last_publication_file = self.data_dir / 'last_tao20_publication.json'
        
        if last_publication_file.exists():
            with open(last_publication_file) as f:
                last_pub = json.load(f)
                last_date = datetime.fromisoformat(last_pub['timestamp'])
                days_since = (datetime.now(timezone.utc) - last_date).days
                
                print(f'📅 Days since last TAO20 publication: {days_since}')
                
                if days_since >= self.rebalance_interval:
                    return True, f'Sunday publication due: {days_since} days since last publication'
                else:
                    return False, f'Only {days_since} days since last publication - need {self.rebalance_interval} days'
        else:
            return True, 'First Sunday TAO20 publication - starting bi-weekly cycle'
    
    def create_tao20_index(self):
        """Generate the TAO20 index using the production system"""
        
        print('🏗️ Generating Sunday TAO20 index...')
        
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
    
    def create_sunday_publication_package(self, index_data):
        """Create Sunday-specific publication package"""
        
        timestamp = datetime.now(timezone.utc)
        date_str = timestamp.strftime('%Y%m%d')
        
        # Create publication directory
        pub_dir = self.data_dir / f'tao20_sunday_{date_str}'
        pub_dir.mkdir(exist_ok=True)
        
        # Calculate next Sunday
        next_sunday = self.get_last_sunday() + timedelta(days=14)
        
        publication_package = {
            'publication_info': {
                'publication_date': timestamp.isoformat(),
                'publication_day': 'Sunday',
                'publication_time': '16:05 UTC',
                'index_name': 'TAO20',
                'index_type': 'Top-20 Concentrated Bittensor Subnet Index',
                'publication_frequency': 'Bi-weekly Sundays',
                'next_publication': next_sunday.isoformat(),
                'data_source': 'AlphaMind Transparent Emissions Collection',
                'methodology': 'Emissions-weighted with strict eligibility requirements'
            },
            'index_composition': index_data,
            'transparency_verification': {
                'daily_emissions_data': 'https://alphamind-emissions-data.s3.amazonaws.com/emissions/',
                'verification_instructions': 'All emissions data can be independently verified via S3 bucket',
                'publication_schedule': 'Every 2 weeks on Sunday at 16:05 UTC',
                'methodology_documentation': 'Detailed methodology available in publication package'
            },
            'regulatory_disclosures': {
                'disclaimer': 'This index is for informational purposes only and does not constitute investment advice',
                'methodology_changes': 'Any methodology changes will be announced with 30-day notice',
                'data_quality': 'All data is cryptographically signed and publicly verifiable',
                'operating_mode': index_data['metadata'].get('operating_mode', 'PRODUCTION'),
                'publication_timing': 'Published 5 minutes after Sunday emissions collection'
            }
        }
        
        # Save complete publication package
        package_file = pub_dir / 'tao20_sunday_publication.json'
        with open(package_file, 'w') as f:
            json.dump(publication_package, f, indent=2)
        
        # Create human-readable summary
        summary_file = pub_dir / 'tao20_sunday_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(self.create_sunday_summary(publication_package))
        
        # Create CSV for easy consumption
        csv_file = pub_dir / 'tao20_weights.csv'
        self.create_csv_export(index_data, csv_file)
        
        print(f'📦 Sunday publication package created: {pub_dir}')
        
        return pub_dir, publication_package
    
    def create_sunday_summary(self, publication_package):
        """Create Sunday-specific human-readable summary"""
        
        summary = f"""
TAO20 SUNDAY INDEX PUBLICATION
==============================
Publication Date: {publication_package['publication_info']['publication_date']}
Schedule: Every 2 weeks on Sunday at 16:05 UTC
Next Publication: {publication_package['publication_info']['next_publication']}

INDEX COMPOSITION (Top 10):
"""
        
        index_data = publication_package['index_composition']
        constituents_key = self.get_constituents_key(index_data)
        
        summary += 'Rank | Subnet | Weight\n'
        summary += '-----|--------|-------\n'
        
        for holding in index_data.get(constituents_key, [])[:10]:
            summary += f'{holding["rank"]:4d} | {holding["netuid"]:6d} | {holding["weight_percentage"]:6.2f}%\n'
        
        summary += f"""
OPERATING MODE: {index_data['metadata'].get('operating_mode', 'PRODUCTION')}

PUBLICATION SCHEDULE:
- Day: Sunday
- Time: 16:05 UTC (5 minutes after data collection)
- Frequency: Every 2 weeks
- Next: {datetime.fromisoformat(publication_package['publication_info']['next_publication']).strftime('%Y-%m-%d %A')}

TRANSPARENCY:
- All daily emissions data: {publication_package['transparency_verification']['daily_emissions_data']}
- Cryptographically signed and publicly verifiable
- Published immediately after Sunday data collection

DISCLAIMER: {publication_package['regulatory_disclosures']['disclaimer']}
"""
        
        return summary
    
    def create_csv_export(self, index_data, csv_file):
        """Create CSV export of index weights"""
        
        constituents_key = self.get_constituents_key(index_data)
        constituents = index_data.get(constituents_key, [])
        
        with open(csv_file, 'w') as f:
            f.write('rank,netuid,weight_percentage,weight_decimal\n')
            for holding in constituents:
                f.write(f'{holding["rank"]},{holding["netuid"]},{holding["weight_percentage"]},{holding["weight"]}\n')
    
    def upload_to_s3(self, pub_dir):
        """Upload Sunday publication to S3"""
        
        print('☁️ Uploading Sunday TAO20 publication to S3...')
        
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        s3_path = f's3://alphamind-emissions-data/tao20_publications/sunday_{date_str}/'
        
        try:
            # Upload publication directory to S3
            result = subprocess.run([
                'aws', 's3', 'sync', str(pub_dir), s3_path,
                '--exclude', '*.pyc'
            ], check=True, capture_output=True, text=True)
            
            print(f'✅ Sunday TAO20 publication uploaded to: {s3_path}')
            
            # Also update latest
            latest_s3_path = 's3://alphamind-emissions-data/tao20_publications/latest_sunday/'
            subprocess.run([
                'aws', 's3', 'sync', str(pub_dir), latest_s3_path,
                '--exclude', '*.pyc'
            ], check=True)
            
            return s3_path
            
        except subprocess.CalledProcessError as e:
            print(f'❌ S3 upload failed: {e.stderr}')
            return None
    
    def record_publication(self, index_data, s3_path):
        """Record successful Sunday publication"""
        
        next_sunday = self.get_last_sunday() + timedelta(days=14)
        
        publication_record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'publication_day': 'Sunday',
            'publication_time': '16:05_UTC',
            'index_metadata': index_data['metadata'],
            's3_publication_url': s3_path,
            'next_publication_due': next_sunday.isoformat(),
            'constituents_count': self.get_constituents_count(index_data),
            'operating_mode': index_data['metadata'].get('operating_mode', 'PRODUCTION')
        }
        
        with open(self.data_dir / 'last_tao20_publication.json', 'w') as f:
            json.dump(publication_record, f, indent=2)
        
        print(f'📝 Sunday publication recorded - next due: {next_sunday.strftime("%Y-%m-%d %A 16:05 UTC")}')
    
    def publish_tao20_sunday_index(self):
        """Main Sunday publication function"""
        
        print('🗓️ TAO20 Sunday Bi-Weekly Publication Check')
        print('=' * 45)
        
        # Check if publication is due
        should_publish, reason = self.should_publish_index()
        
        print(f'📅 Sunday publication check: {reason}')
        
        if not should_publish:
            print('⏳ TAO20 Sunday publication not due yet')
            return False
        
        print('🎯 Sunday TAO20 publication starting...')
        
        # Generate the index
        index_data = self.create_tao20_index()
        if not index_data:
            print('❌ Failed to generate TAO20 index')
            return False
        
        # Create Sunday publication package
        pub_dir, publication_package = self.create_sunday_publication_package(index_data)
        
        # Upload to S3 for transparency
        s3_path = self.upload_to_s3(pub_dir)
        
        if s3_path:
            # Record successful publication
            self.record_publication(index_data, s3_path)
            
            next_sunday = self.get_last_sunday() + timedelta(days=14)
            
            print('\n' + '=' * 60)
            print('🎉 TAO20 SUNDAY INDEX PUBLISHED!')
            print('=' * 60)
            print(f'📅 Published: {datetime.now(timezone.utc).strftime("%Y-%m-%d %A %H:%M UTC")}')
            print(f'🌐 Public URL: {s3_path}')
            print(f'📊 Constituents: {self.get_constituents_count(index_data)}')
            print(f'🎯 Mode: {index_data["metadata"].get("operating_mode", "PRODUCTION")}')
            print(f'📅 Next Sunday: {next_sunday.strftime("%Y-%m-%d %A 16:05 UTC")}')
            
            return True
        else:
            print('❌ Sunday publication failed due to S3 upload error')
            return False

def main():
    os.chdir('/opt/alphamind/src')
    
    publisher = TAO20SundayPublisher()
    
    try:
        return publisher.publish_tao20_sunday_index()
    except Exception as e:
        print(f'❌ Sunday publication error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
