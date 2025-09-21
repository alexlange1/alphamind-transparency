#!/bin/bash
# TAO20 CPS VPS Fix Script
# Run this script on your VPS to fix the emissions collection issue

set -e  # Exit on any error

echo "🚀 TAO20 CPS VPS TROUBLESHOOTING SCRIPT"
echo "======================================"
echo "Starting VPS diagnostics at $(date)"
echo ""

# Function to check command success
check_success() {
    if [ $? -eq 0 ]; then
        echo "✅ $1"
    else
        echo "❌ $1"
        echo "Script failed. Please check the error above and fix it manually."
        exit 1
    fi
}

# 1. Update system
echo "1. Updating system packages..."
sudo apt update && sudo apt upgrade -y
check_success "System updated"

# 2. Install Python and pip if needed
echo ""
echo "2. Installing Python and pip..."
sudo apt install -y python3 python3-pip python3-venv
check_success "Python installed"

# 3. Install btcli (Bittensor CLI)
echo ""
echo "3. Installing btcli..."
curl -fsSL https://raw.githubusercontent.com/opentensor/bittensor/main/scripts/install.sh | bash
check_success "btcli installed"

# 4. Reload shell environment
echo ""
echo "4. Reloading shell environment..."
source ~/.bashrc
which btcli > /dev/null
check_success "btcli is in PATH"

# 5. Show btcli version
echo ""
echo "5. Checking btcli version..."
btcli --version
check_success "btcli version check"

# 6. Find the project directory
echo ""
echo "6. Finding project directory..."
PROJECT_DIR=$(find /home -name "alphamind-transparency" -type d 2>/dev/null | head -1)
if [ -z "$PROJECT_DIR" ]; then
    PROJECT_DIR="/home/$(whoami)/alphamind-transparency"
    echo "Project directory not found. Using default: $PROJECT_DIR"
    echo "Please update PROJECT_DIR variable if this is incorrect."
fi

echo "Project directory: $PROJECT_DIR"

# 7. Navigate to project and check files
echo ""
echo "7. Checking project files..."
cd "$PROJECT_DIR"
pwd
ls -la
check_success "Project directory access"

# 8. Install Python dependencies
echo ""
echo "8. Installing Python dependencies..."
pip3 install -r requirements.txt
check_success "Dependencies installed"

# 9. Set environment variables (you'll need to fill these in)
echo ""
echo "9. Setting environment variables..."
echo "Please set your GitHub token and Discord webhook:"
echo "export GITHUB_TOKEN='your_github_token_here'"
echo "export DISCORD_WEBHOOK_URL='your_discord_webhook_here'"
echo ""
echo "For now, let's test without them..."

# 10. Test btcli connectivity
echo ""
echo "10. Testing btcli connectivity..."
timeout 30 btcli subnet list --network finney --json-output | head -c 100
if [ $? -eq 0 ]; then
    echo ""
    check_success "btcli connectivity test"
else
    echo ""
    echo "⚠️ btcli connectivity test failed or timed out"
    echo "This might be normal - let's continue with the script test"
fi

# 11. Test emissions script
echo ""
echo "11. Testing emissions collection script..."
python3 scripts/fetch_emissions.py

if [ $? -eq 0 ]; then
    check_success "Emissions script test completed"
    echo ""
    echo "🎉 SUCCESS! The emissions collection is now working!"
    echo ""
    echo "Next steps:"
    echo "1. Set your environment variables:"
    echo "   export GITHUB_TOKEN='your_actual_github_token'"
    echo "   export DISCORD_WEBHOOK_URL='your_actual_discord_webhook'"
    echo ""
    echo "2. Test with GitHub integration:"
    echo "   python3 scripts/fetch_emissions.py"
    echo ""
    echo "3. Check that files appear in emissions/ folder"
    echo "4. Verify files are pushed to GitHub"
else
    echo ""
    echo "⚠️ Emissions script test had issues"
    echo "Check the error output above for details"
fi

# 12. Check cron job status
echo ""
echo "12. Checking cron job status..."
crontab -l | grep -i emission || echo "No emissions cron job found"
sudo systemctl status cron --no-pager

echo ""
echo "=== TROUBLESHOOTING COMPLETE ==="
echo "Script finished at $(date)"
echo ""
echo "If you encountered any errors, please share them with me for further assistance."
