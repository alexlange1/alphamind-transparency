#!/usr/bin/env python3
"""
TAO20 CPS Utilities
GitHub operations, Discord notifications, and checksum utilities
"""

import hashlib
import json
import os
import subprocess
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

class GitHubManager:
    def __init__(self, repo_path: str, github_token: str):
        self.repo_path = repo_path
        self.github_token = github_token
        self.git_config = {
            'user.name': 'TAO20 CPS Bot',
            'user.email': 'tao20-cps@alphamind.ai'
        }
    
    def setup_git_config(self):
        """Configure git for automated commits"""
        for key, value in self.git_config.items():
            subprocess.run(['git', 'config', key, value], check=True)
    
    def add_and_commit(self, files: list, message: str) -> bool:
        """Add files and commit with message"""
        try:
            # Add files
            for file_path in files:
                subprocess.run(['git', 'add', str(file_path)], check=True)
            
            # Commit
            subprocess.run(['git', 'commit', '-m', message], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Git commit failed: {e}")
            return False
    
    def push_to_github(self) -> bool:
        """Push commits to GitHub"""
        try:
            subprocess.run(['git', 'push', 'origin', 'main'], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Git push failed: {e}")
            return False
    
    def get_commit_hash(self) -> str:
        """Get the latest commit hash"""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()[:8]
        except subprocess.CalledProcessError:
            return "unknown"

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_emissions_success(self, filename: str, checksum: str, subnet_count: int):
        """Send success notification for emissions collection"""
        embed = {
            "title": "✅ Daily Emissions Collection Success",
            "color": 0x00ff00,
            "fields": [
                {"name": "📁 File", "value": filename, "inline": True},
                {"name": "🔢 Subnets", "value": str(subnet_count), "inline": True},
                {"name": "🔐 SHA256", "value": f"`{checksum}`", "inline": False},
                {"name": "⏰ Time", "value": f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", "inline": False}
            ],
            "footer": {"text": "TAO20 CPS - GitHub Transparency"}
        }
        self._send_webhook(embed)
    
    def send_emissions_error(self, error_msg: str):
        """Send error notification for emissions collection"""
        embed = {
            "title": "❌ Daily Emissions Collection Failed",
            "color": 0xff0000,
            "fields": [
                {"name": "Error", "value": error_msg, "inline": False},
                {"name": "⏰ Time", "value": f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", "inline": False}
            ],
            "footer": {"text": "TAO20 CPS - GitHub Transparency"}
        }
        self._send_webhook(embed)
    
    def send_tao20_success(self, date: str, top_3: list, checksum: str, github_url: str):
        """Send success notification for TAO20 rebalancing"""
        top_3_text = "\n".join([f"{i+1}. Subnet {item['netuid']}: {item['weight']:.2f}%" 
                               for i, item in enumerate(top_3)])
        
        embed = {
            "title": "🎯 TAO20 Rebalancing Complete",
            "color": 0x0099ff,
            "fields": [
                {"name": "📅 Rebalance Date", "value": date, "inline": True},
                {"name": "🏆 Top 3 Subnets", "value": top_3_text, "inline": False},
                {"name": "🔐 SHA256", "value": f"`{checksum}`", "inline": False},
                {"name": "🔗 GitHub Files", "value": f"[View Files]({github_url})", "inline": False},
                {"name": "⏰ Time", "value": f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", "inline": False}
            ],
            "footer": {"text": "TAO20 CPS - GitHub Transparency"}
        }
        self._send_webhook(embed)
    
    def send_tao20_error(self, error_msg: str):
        """Send error notification for TAO20 rebalancing"""
        embed = {
            "title": "❌ TAO20 Rebalancing Failed",
            "color": 0xff0000,
            "fields": [
                {"name": "Error", "value": error_msg, "inline": False},
                {"name": "⏰ Time", "value": f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", "inline": False}
            ],
            "footer": {"text": "TAO20 CPS - GitHub Transparency"}
        }
        self._send_webhook(embed)
    
    def _send_webhook(self, embed: Dict[str, Any]):
        """Send webhook to Discord"""
        if not self.webhook_url:
            print("⚠️ No Discord webhook URL configured")
            return
        
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            print("✅ Discord notification sent")
        except Exception as e:
            print(f"❌ Discord notification failed: {e}")

class ChecksumManager:
    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calculate SHA256 checksum of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    @staticmethod
    def save_checksum(file_path: Path, checksum: str):
        """Save checksum to .sha256 file"""
        checksum_file = file_path.with_suffix(file_path.suffix + '.sha256')
        with open(checksum_file, 'w') as f:
            f.write(checksum)
        return checksum_file
    
    @staticmethod
    def verify_checksum(file_path: Path) -> bool:
        """Verify file against its checksum"""
        checksum_file = file_path.with_suffix(file_path.suffix + '.sha256')
        if not checksum_file.exists():
            return False
        
        with open(checksum_file, 'r') as f:
            stored_checksum = f.read().strip()
        
        calculated_checksum = ChecksumManager.calculate_sha256(file_path)
        return stored_checksum == calculated_checksum

def load_config() -> Dict[str, str]:
    """Load configuration from environment variables"""
    config = {
        'github_token': os.getenv('GITHUB_TOKEN', ''),
        'discord_webhook': os.getenv('DISCORD_WEBHOOK_URL', ''),
        'repo_path': os.getenv('REPO_PATH', '.'),
    }
    
    # Validate required config
    if not config['github_token']:
        print("⚠️ Warning: GITHUB_TOKEN not set")
    if not config['discord_webhook']:
        print("⚠️ Warning: DISCORD_WEBHOOK_URL not set")
    
    return config

def setup_logging():
    """Setup logging for the scripts"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    return log_dir
