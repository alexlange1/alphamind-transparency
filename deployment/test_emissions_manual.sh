#!/bin/bash
set -euo pipefail

# Manual Test Script for AlphaMind Emissions Collection
# Run this to manually test emissions collection on VPS

echo "🧪 MANUAL EMISSIONS COLLECTION TEST"
echo "===================================="
echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# Check if running as alphamind user
if [ "$(whoami)" = "alphamind" ]; then
    echo "✅ Running as alphamind user"
else
    echo "🔄 Switching to alphamind user..."
    exec sudo -u alphamind "$0" "$@"
fi

# Set up environment
cd /opt/alphamind/src
echo "📁 Working directory: $(pwd)"

# Load environment variables
if [ -f /etc/alphamind/env ]; then
    source /etc/alphamind/env
    echo "✅ Environment loaded"
else
    echo "⚠️  No environment file found at /etc/alphamind/env"
fi

# Load HMAC key
if [ -f /etc/alphamind/hmac_v2.b64 ]; then
    export ALPHAMIND_SECRET_KEY_B64="$(cat /etc/alphamind/hmac_v2.b64)"
    echo "✅ HMAC key loaded"
else
    echo "⚠️  No HMAC key found at /etc/alphamind/hmac_v2.b64"
fi

# Activate Python environment
if [ -f /opt/alphamind/venv/bin/activate ]; then
    source /opt/alphamind/venv/bin/activate
    echo "✅ Python virtual environment activated"
    echo "🐍 Python version: $(python3 --version)"
else
    echo "❌ Virtual environment not found"
    exit 1
fi

# Test btcli availability
echo ""
echo "🔧 TESTING BTCLI"
echo "================="
if which btcli >/dev/null 2>&1; then
    echo "✅ btcli found at: $(which btcli)"
    
    echo "🔍 Testing btcli help..."
    if timeout 5 btcli --help >/dev/null 2>&1; then
        echo "✅ btcli responds to --help"
    else
        echo "❌ btcli not responding or hanging"
        exit 1
    fi
    
    echo "🔍 Testing network connectivity (30 second timeout)..."
    if timeout 30 btcli subnets list --network finney --json-output >/dev/null 2>&1; then
        echo "✅ btcli can connect to finney network"
    else
        echo "❌ btcli cannot connect to finney network"
        echo "💡 Check internet connection and firewall settings"
        exit 1
    fi
else
    echo "❌ btcli not found"
    echo "💡 Try: pip install bittensor btcli"
    exit 1
fi

# Create output directory
mkdir -p out/secure/secure_data
echo "✅ Output directory created"

# Test basic emissions collection
echo ""
echo "📊 TESTING EMISSIONS COLLECTION"
echo "==============================="
echo "🔍 Running basic emissions test..."

python3 -c "
import sys
sys.path.insert(0, '.')
from emissions.snapshot import take_snapshot_map
print('📡 Fetching emissions data...')
emissions = take_snapshot_map()
print(f'✅ Retrieved emissions for {len(emissions)} subnets')
if emissions:
    print('📈 Sample data:')
    for netuid, daily_emission in list(emissions.items())[:3]:
        print(f'  Subnet {netuid}: {daily_emission:.2f} TAO/day')
else:
    print('❌ No emissions data retrieved')
    sys.exit(1)
"

# Test full daily collection script
echo ""
echo "🚀 TESTING FULL COLLECTION SCRIPT"
echo "================================="
echo "🔍 Running daily emissions collection script..."

if python3 scripts/daily_emissions_collection.py; then
    echo "✅ Daily emissions collection completed successfully"
    
    # Check output files
    echo ""
    echo "📁 CHECKING OUTPUT FILES"
    echo "========================"
    
    if [ -f out/secure/secure_data/latest_emissions_secure.json ]; then
        echo "✅ Latest emissions file created"
        echo "📊 File size: $(stat -c%s out/secure/secure_data/latest_emissions_secure.json) bytes"
        
        # Show basic stats
        python3 -c "
import json
with open('out/secure/secure_data/latest_emissions_secure.json') as f:
    data = json.load(f)
print(f'📅 Timestamp: {data[\"timestamp\"]}')
print(f'📊 Total subnets: {data[\"total_subnets\"]}')
print(f'🔐 Content hash: {data[\"content_hash\"][:16]}...')
"
    else
        echo "❌ No latest emissions file found"
    fi
    
else
    echo "❌ Daily emissions collection failed"
    exit 1
fi

echo ""
echo "🎉 MANUAL TEST COMPLETED SUCCESSFULLY!"
echo "======================================"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Configure AWS credentials (if not done):"
echo "   aws configure"
echo ""
echo "2. Test S3 upload:"
echo "   aws s3 ls s3://\${S3_BUCKET}/ || echo 'Configure S3_BUCKET in /etc/alphamind/env'"
echo ""
echo "3. Start automated collection:"
echo "   sudo systemctl start alphamind-emissions.timer"
echo "   sudo systemctl status alphamind-emissions.timer"
echo ""
echo "4. Monitor logs:"
echo "   sudo journalctl -u alphamind-emissions.service -f"
echo ""
echo "✨ Your VPS is ready for automated emissions collection!"
