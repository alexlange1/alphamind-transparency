#!/bin/bash
# Commands to run on VPS (138.68.69.71) to deploy GitHub sync for emissions data

echo "🚀 Deploying GitHub Sync for Emissions Data to VPS"
echo "=================================================="

echo "🎯 AUTOMATED DEPLOYMENT (Recommended):"
echo "bash deployment/deploy_github_sync_to_vps.sh"
echo ""

echo "📋 MANUAL DEPLOYMENT STEPS:"
echo ""

echo "Step 1: SSH to VPS and switch to alphamind user"
echo "ssh root@138.68.69.71"
echo "sudo -u alphamind -i"
echo ""

echo "Step 2: Navigate to project directory and pull latest changes"
echo "cd /opt/alphamind"
echo "git pull origin main"
echo "chmod +x deployment/vps/github_sync.sh"
echo ""

echo "Step 3: Create emissions-data directory structure"
echo "mkdir -p emissions-data/daily emissions-data/secure emissions-data/manifests"
echo ""

echo "Step 4: Configure Git for automated commits"
echo "git config --global user.name 'AlphaMind VPS Bot'"
echo "git config --global user.email 'alphamind-vps@alexlange.dev'"
echo ""

echo "Step 5: Test the new GitHub sync system"
echo "bash deployment/vps/github_sync.sh"
echo ""

echo "Step 6: Restart services (as root)"
echo "exit  # back to root"
echo "sudo systemctl restart alphamind-emissions.service"
echo "sudo systemctl status alphamind-emissions.service"
echo "sudo systemctl list-timers alphamind-emissions.timer"
echo ""

echo "✅ WHAT CHANGED:"
echo "  🔄 Emissions data now uploads to GitHub instead of S3"
echo "  📁 Creates organized emissions-data/ directory structure" 
echo "  🔀 Automatic pull requests for transparency"
echo "  🔗 Public data at: https://github.com/alexlange1/alphamind"
echo ""

echo "📅 Next collection at 16:00 UTC will upload to GitHub!"
echo "🎉 Full transparency and public verification enabled!"

