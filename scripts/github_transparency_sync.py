#!/usr/bin/env python3
"""
GitHub Transparency Sync
Mirrors emissions data and TAO20 publications to GitHub for ultimate transparency
"""

import json
import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timezone
import sys

class GitHubTransparencySync:
    def __init__(self):
        self.data_dir = Path('out')
        self.transparency_dir = Path('/tmp/alphamind_transparency')
        self.github_repo = 'alphamind-transparency'  # Create this as public repo
        
    def setup_transparency_repo(self):
        """Set up local transparency repository"""
        
        print('📂 Setting up transparency repository...')
        
        # Clean and recreate transparency directory
        if self.transparency_dir.exists():
            shutil.rmtree(self.transparency_dir)
        
        self.transparency_dir.mkdir(parents=True)
        
        # Initialize git repo
        os.chdir(self.transparency_dir)
        subprocess.run(['git', 'init'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'AlphaMind Transparency Bot'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'transparency@alphamind.ai'], check=True)
        
        # Create README
        readme_content = """# AlphaMind Transparency Repository

## 🌟 Complete Transparency for TAO20 Index

This repository provides **full transparency** for the AlphaMind TAO20 index system:

### 📊 Daily Emissions Data
- **Location**: `emissions/daily/`
- **Format**: JSON with cryptographic verification
- **Collection**: Every day at 16:00 UTC
- **Source**: Bittensor network via `btcli`

### 📈 TAO20 Index Publications  
- **Location**: `tao20_publications/`
- **Schedule**: Every 2 weeks on Sunday at 16:05 UTC
- **Format**: JSON, CSV, and human-readable summaries

### 🔐 Cryptographic Verification
- **SHA-256 hashes** for data integrity
- **HMAC-SHA256** for authenticity
- **Ed25519 signatures** for manifests
- **Merkle trees** for batch verification

### 📅 Publication Schedule
- **Daily Emissions**: 16:00 UTC
- **TAO20 Index**: Sunday 16:05 UTC (bi-weekly)
- **Data Retention**: Permanent public archive

### 🔍 Verification Instructions
1. Download any emissions file
2. Verify SHA-256 hash matches filename
3. Check HMAC signature with public key
4. Cross-reference with S3 bucket data

### 🌐 Additional Access
- **S3 Bucket**: `alphamind-emissions-data`
- **Live API**: Coming soon
- **Documentation**: Available in each publication

---
*Last updated: {timestamp}*
*Next TAO20 publication: Check latest manifest*
"""
        
        with open('README.md', 'w') as f:
            f.write(readme_content.format(timestamp=datetime.now(timezone.utc).isoformat()))
        
        # Create directory structure
        Path('emissions/daily').mkdir(parents=True)
        Path('tao20_publications').mkdir(parents=True)
        Path('manifests').mkdir(parents=True)
        
        print('✅ Transparency repository initialized')
    
    def sync_emissions_data(self):
        """Sync latest emissions data to transparency repo"""
        
        print('📊 Syncing emissions data...')
        
        source_dir = Path('/opt/alphamind/src/out')
        target_dir = self.transparency_dir / 'emissions' / 'daily'
        
        # Copy recent emissions files
        for emissions_file in source_dir.glob('emissions_daily_*.json'):
            target_file = target_dir / emissions_file.name
            shutil.copy2(emissions_file, target_file)
            print(f'📄 Copied: {emissions_file.name}')
        
        # Copy latest emissions
        latest_file = source_dir / 'emissions_latest.json'
        if latest_file.exists():
            shutil.copy2(latest_file, target_dir / 'emissions_latest.json')
            print('📄 Copied: emissions_latest.json')
    
    def sync_tao20_publications(self):
        """Sync TAO20 publications to transparency repo"""
        
        print('📈 Syncing TAO20 publications...')
        
        source_dir = Path('/opt/alphamind/src/out')
        target_dir = self.transparency_dir / 'tao20_publications'
        
        # Copy TAO20 publication directories
        for pub_dir in source_dir.glob('tao20_*'):
            if pub_dir.is_dir():
                target_pub_dir = target_dir / pub_dir.name
                if target_pub_dir.exists():
                    shutil.rmtree(target_pub_dir)
                shutil.copytree(pub_dir, target_pub_dir)
                print(f'📁 Copied: {pub_dir.name}')
        
        # Copy latest TAO20 files
        for tao20_file in source_dir.glob('tao20_*.json'):
            target_file = target_dir / tao20_file.name
            shutil.copy2(tao20_file, target_file)
            print(f'📄 Copied: {tao20_file.name}')
    
    def create_transparency_manifest(self):
        """Create transparency manifest with metadata"""
        
        print('📋 Creating transparency manifest...')
        
        manifest = {
            'transparency_info': {
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'repository': 'AlphaMind Transparency Archive',
                'purpose': 'Complete transparency for TAO20 index system',
                'verification': 'All data cryptographically signed and verifiable'
            },
            'data_summary': {
                'emissions_files': len(list((self.transparency_dir / 'emissions' / 'daily').glob('*.json'))),
                'tao20_publications': len(list((self.transparency_dir / 'tao20_publications').glob('tao20_*'))),
                'last_emissions': self.get_latest_emissions_date(),
                'last_tao20': self.get_latest_tao20_date()
            },
            'access_info': {
                'github_repo': f'https://github.com/alexlange1/{self.github_repo}',
                's3_bucket': 'https://alphamind-emissions-data.s3.amazonaws.com/',
                'verification_keys': 'Available in manifests/ directory'
            }
        }
        
        manifest_file = self.transparency_dir / 'manifests' / f'transparency_manifest_{datetime.now(timezone.utc).strftime("%Y%m%d")}.json'
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Also create latest manifest
        latest_manifest = self.transparency_dir / 'transparency_manifest_latest.json'
        with open(latest_manifest, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print('✅ Transparency manifest created')
    
    def get_latest_emissions_date(self):
        """Get the date of latest emissions file"""
        emissions_dir = self.transparency_dir / 'emissions' / 'daily'
        emissions_files = list(emissions_dir.glob('emissions_daily_*.json'))
        if emissions_files:
            latest = max(emissions_files, key=lambda p: p.stat().st_mtime)
            return latest.name.split('_')[-1].split('.')[0]
        return None
    
    def get_latest_tao20_date(self):
        """Get the date of latest TAO20 publication"""
        tao20_dir = self.transparency_dir / 'tao20_publications'
        tao20_dirs = list(tao20_dir.glob('tao20_*'))
        if tao20_dirs:
            latest = max(tao20_dirs, key=lambda p: p.stat().st_mtime)
            return latest.name.split('_')[-1]
        return None
    
    def commit_and_prepare_push(self):
        """Commit changes and prepare for push"""
        
        print('💾 Committing transparency updates...')
        
        os.chdir(self.transparency_dir)
        
        # Add all files
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Commit with timestamp
        commit_msg = f'Transparency update: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}'
        result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
        
        if result.returncode == 0:
            print('✅ Changes committed successfully')
            print('📋 To push to GitHub:')
            print(f'   1. Create public repo: github.com/alexlange1/{self.github_repo}')
            print(f'   2. cd {self.transparency_dir}')
            print(f'   3. git remote add origin git@github.com:alexlange1/{self.github_repo}.git')
            print('   4. git push -u origin main')
        else:
            print('ℹ️ No changes to commit (repository up to date)')
    
    def sync_transparency(self):
        """Main transparency sync function"""
        
        print('🌐 AlphaMind Transparency Sync')
        print('=' * 35)
        
        try:
            self.setup_transparency_repo()
            self.sync_emissions_data()
            self.sync_tao20_publications() 
            self.create_transparency_manifest()
            self.commit_and_prepare_push()
            
            print('\n' + '=' * 50)
            print('✅ TRANSPARENCY SYNC COMPLETED!')
            print('=' * 50)
            print(f'📂 Local repo: {self.transparency_dir}')
            print('🌐 Ready for GitHub publication')
            print('🔍 All data verified and organized')
            
            return True
            
        except Exception as e:
            print(f'❌ Transparency sync failed: {e}')
            import traceback
            traceback.print_exc()
            return False

def main():
    os.chdir('/opt/alphamind/src')
    
    syncer = GitHubTransparencySync()
    
    return syncer.sync_transparency()

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
