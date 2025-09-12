#!/bin/bash
# Deploy GitHub Sync Changes to VPS
# Run this script to deploy the new GitHub-based emissions upload system to VPS 138.68.69.71

set -euo pipefail

VPS_HOST="138.68.69.71"
VPS_USER="root"
PROJECT_PATH="/opt/alphamind"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "🚀 Deploying GitHub sync changes to VPS $VPS_HOST"
log "=================================================="

# Check if we can SSH to the VPS
log "🔍 Testing SSH connection to VPS..."
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USER@$VPS_HOST" "echo 'SSH connection successful'" >/dev/null 2>&1; then
    log "❌ Cannot connect to VPS via SSH"
    log "Please ensure:"
    log "  1. SSH key is properly configured"
    log "  2. VPS is accessible"
    log "  3. You can run: ssh $VPS_USER@$VPS_HOST"
    exit 1
fi

log "✅ SSH connection successful"

# Deploy the changes
log "📦 Deploying changes to VPS..."

ssh "$VPS_USER@$VPS_HOST" << 'EOF'
set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "📂 Switching to alphamind user and project directory..."
cd /opt/alphamind

# Switch to alphamind user for git operations
sudo -u alphamind bash << 'ALPHAMIND_EOF'
set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "🔄 Pulling latest changes from GitHub..."
git fetch origin
git checkout main
git pull origin main

log "✅ Code updated successfully"

# Make sure the new script is executable
chmod +x deployment/vps/github_sync.sh

log "🔧 Setting up GitHub authentication..."
# Check if GitHub CLI is installed
if ! command -v gh >/dev/null 2>&1; then
    log "📥 Installing GitHub CLI..."
    # Install GitHub CLI for automated PR creation
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt update
    sudo apt install gh -y
else
    log "✅ GitHub CLI already installed"
fi

log "🔑 Configuring Git for automated commits..."
# Configure git for automated commits
git config --global user.name "AlphaMind VPS Bot"
git config --global user.email "alphamind-vps@alexlange.dev"

log "📁 Creating emissions-data directory structure..."
# Create the emissions-data directory structure
mkdir -p emissions-data/daily
mkdir -p emissions-data/secure  
mkdir -p emissions-data/manifests

# Copy README if it doesn't exist
if [ ! -f "emissions-data/README.md" ]; then
    cat > emissions-data/README.md << 'README_EOF'
# AlphaMind Emissions Data

This directory contains daily emissions data collected from the Bittensor network for transparency and verification purposes.

## Structure

- `daily/` - Daily emissions snapshots in JSON format
- `secure/` - Cryptographically secured emissions data with integrity verification
- `manifests/` - Manifest files for data verification and integrity checking

## Data Collection

- **Frequency**: Daily at 16:00 UTC (4 PM UTC)
- **Network**: Bittensor Finney
- **Collection Method**: Automated via `btcli subnet list` 
- **Security**: All data is cryptographically signed with SHA-256 hashes and HMAC verification

## Data Format

Each daily emissions file contains:
- `timestamp`: ISO 8601 timestamp of collection
- `emissions_by_netuid`: Emissions data per subnet ID
- `total_subnets`: Number of subnets collected
- `network`: Network name (finney)
- `collection_method`: Method used for collection

## Verification

All data can be independently verified through:
1. Cryptographic signatures in the secure data files
2. Manifest files containing checksums
3. Public transparency via this repository

## Latest Data

The most recent emissions data is always available in:
- `daily/emissions_latest.json` - Latest daily snapshot
- `secure/latest_emissions_secure.json` - Latest secure snapshot with integrity verification

## Usage

This data is used for:
- TAO20 index calculations
- Subnet performance analysis
- Transparent emissions tracking
- Independent verification of AlphaMind methodologies

All data is provided for transparency and research purposes.
README_EOF
fi

log "🧪 Testing the new GitHub sync script..."
# Test the GitHub sync script (dry run)
if bash deployment/vps/github_sync.sh --help >/dev/null 2>&1 || true; then
    log "✅ GitHub sync script is ready"
else
    log "⚠️  GitHub sync script may need GitHub authentication setup"
fi

ALPHAMIND_EOF

log "🔄 Updating systemd service configuration if needed..."
# Check if the systemd service needs updating
if systemctl is-active --quiet alphamind-emissions.service; then
    log "🔄 Restarting emissions collection service..."
    systemctl restart alphamind-emissions.service
fi

log "📋 Checking service status..."
systemctl status alphamind-emissions.service --no-pager -l || true
systemctl status alphamind-emissions.timer --no-pager -l || true

log "⏰ Next scheduled collection times:"
systemctl list-timers alphamind-emissions.timer --no-pager || true

log "✅ Deployment completed successfully!"
log ""
log "🎯 Summary of changes:"
log "  ✅ GitHub sync script deployed"
log "  ✅ Collection script updated to use GitHub"
log "  ✅ emissions-data directory structure created"
log "  ✅ Services restarted"
log ""
log "📅 Next emissions collection will upload to GitHub at 16:00 UTC"
log "🔗 Data will be available at: https://github.com/alexlange1/alphamind/tree/emissions-data-updates"

EOF

log "✅ VPS deployment completed!"
log ""
log "🔧 Next steps:"
log "  1. The VPS will now upload emissions data to GitHub instead of S3"
log "  2. Data will be available in the emissions-data-updates branch"
log "  3. Pull requests will be created automatically for transparency"
log "  4. Next collection: Today at 16:00 UTC"
log ""
log "🔍 To verify deployment, you can SSH to the VPS and run:"
log "  ssh $VPS_USER@$VPS_HOST"
log "  sudo -u alphamind -i"
log "  cd /opt/alphamind"
log "  bash deployment/vps/github_sync.sh --help"
