#!/bin/bash
set -euo pipefail

# VPS Debug Script for AlphaMind Emissions Collection
# Run this on your Digital Ocean VPS to diagnose issues

echo "🔧 ALPHAMIND VPS DIAGNOSTIC TOOL"
echo "================================="
echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# Function to check and report status
check_status() {
    local service="$1"
    local command="$2"
    echo -n "🔍 Checking $service... "
    if eval "$command" &>/dev/null; then
        echo "✅ OK"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

# Function to run command as alphamind user
run_as_alphamind() {
    sudo -u alphamind "$@"
}

echo "📋 SYSTEM INFORMATION"
echo "====================="
echo "OS: $(lsb_release -d | cut -f2)"
echo "Hostname: $(hostname)"
echo "User: $(whoami)"
echo "Working Directory: $(pwd)"
echo ""

echo "👤 USER & PERMISSIONS CHECK"
echo "============================"
check_status "alphamind user exists" "id alphamind"
check_status "/opt/alphamind directory exists" "[ -d /opt/alphamind ]"
check_status "/opt/alphamind ownership" "[ -O /opt/alphamind ] || sudo -u alphamind [ -w /opt/alphamind ]"
check_status "/etc/alphamind config directory" "[ -d /etc/alphamind ]"
echo ""

echo "🐍 PYTHON ENVIRONMENT CHECK"
echo "============================"
check_status "Python virtual environment" "[ -f /opt/alphamind/venv/bin/activate ]"
if [ -f /opt/alphamind/venv/bin/activate ]; then
    echo "🔍 Testing Python environment activation..."
    run_as_alphamind bash -c "source /opt/alphamind/venv/bin/activate && python3 --version"
    
    echo "🔍 Checking Python packages..."
    run_as_alphamind bash -c "source /opt/alphamind/venv/bin/activate && pip list | grep -E '(bittensor|cryptography|boto3)'"
fi
echo ""

echo "🔗 BTCLI INSTALLATION CHECK"
echo "============================"
if [ -f /opt/alphamind/venv/bin/activate ]; then
    echo "🔍 Testing btcli installation..."
    if run_as_alphamind bash -c "source /opt/alphamind/venv/bin/activate && which btcli" &>/dev/null; then
        BTCLI_PATH=$(run_as_alphamind bash -c "source /opt/alphamind/venv/bin/activate && which btcli")
        echo "✅ btcli found at: $BTCLI_PATH"
        
        echo "🔍 Testing btcli functionality..."
        if run_as_alphamind bash -c "source /opt/alphamind/venv/bin/activate && timeout 10 btcli --help" &>/dev/null; then
            echo "✅ btcli responds to --help"
        else
            echo "❌ btcli not responding or hanging"
        fi
        
        echo "🔍 Testing network connectivity..."
        if run_as_alphamind bash -c "source /opt/alphamind/venv/bin/activate && timeout 30 btcli subnets list --network finney --json-output" &>/dev/null; then
            echo "✅ btcli can connect to finney network"
        else
            echo "❌ btcli cannot connect to finney network (check internet/firewall)"
        fi
    else
        echo "❌ btcli not found in virtual environment"
        echo "💡 Try: sudo -u alphamind bash -c 'source /opt/alphamind/venv/bin/activate && pip install bittensor btcli'"
    fi
else
    echo "❌ Virtual environment not found"
fi
echo ""

echo "📁 REPOSITORY & SOURCE CODE CHECK"
echo "=================================="
check_status "Source directory exists" "[ -d /opt/alphamind/src ]"
if [ -d /opt/alphamind/src ]; then
    echo "🔍 Repository status:"
    run_as_alphamind bash -c "cd /opt/alphamind/src && git status --porcelain" || echo "❌ Git repository issues"
    echo "🔍 Current branch:"
    run_as_alphamind bash -c "cd /opt/alphamind/src && git branch --show-current" || echo "❌ Cannot determine branch"
    
    echo "🔍 Key files:"
    for file in "scripts/daily_emissions_collection.py" "emissions/snapshot.py" "requirements.txt"; do
        if [ -f "/opt/alphamind/src/$file" ]; then
            echo "✅ $file exists"
        else
            echo "❌ $file missing"
        fi
    done
fi
echo ""

echo "🔐 SECURITY CONFIGURATION CHECK"
echo "==============================="
check_status "HMAC key exists" "[ -f /etc/alphamind/hmac_v2.b64 ]"
check_status "Environment config exists" "[ -f /etc/alphamind/env ]"
if [ -f /etc/alphamind/env ]; then
    echo "🔍 Environment variables configured:"
    while IFS= read -r line; do
        if [[ $line =~ ^[A-Z_]+=.+ ]] && [[ ! $line =~ PASSWORD|SECRET|KEY ]]; then
            echo "  ✅ $line"
        fi
    done < /etc/alphamind/env
fi
echo ""

echo "⏰ SYSTEMD AUTOMATION CHECK"
echo "============================"
check_status "systemd service exists" "[ -f /etc/systemd/system/alphamind-emissions.service ]"
check_status "systemd timer exists" "[ -f /etc/systemd/system/alphamind-emissions.timer ]"
check_status "timer enabled" "systemctl is-enabled alphamind-emissions.timer"
check_status "timer active" "systemctl is-active alphamind-emissions.timer"

echo "🔍 Timer schedule:"
systemctl list-timers alphamind-emissions.timer 2>/dev/null || echo "❌ Timer not found"
echo ""

echo "📋 RUNNER SCRIPT CHECK"
echo "======================"
check_status "Daily runner script exists" "[ -f /opt/alphamind/run_daily.sh ]"
check_status "Runner script executable" "[ -x /opt/alphamind/run_daily.sh ]"
echo ""

echo "☁️ AWS CONFIGURATION CHECK"
echo "=========================="
if run_as_alphamind bash -c "aws --version" &>/dev/null; then
    echo "✅ AWS CLI installed"
    if run_as_alphamind bash -c "aws sts get-caller-identity" &>/dev/null; then
        echo "✅ AWS credentials configured"
        echo "🔍 AWS identity:"
        run_as_alphamind aws sts get-caller-identity 2>/dev/null || echo "❌ Cannot get AWS identity"
    else
        echo "❌ AWS credentials not configured"
        echo "💡 Run: sudo -u alphamind aws configure"
    fi
else
    echo "❌ AWS CLI not installed"
fi
echo ""

echo "📊 OUTPUT DIRECTORIES CHECK"
echo "==========================="
run_as_alphamind mkdir -p /opt/alphamind/src/out/secure/secure_data
check_status "Output directory writable" "run_as_alphamind touch /opt/alphamind/src/out/secure/secure_data/test.tmp && run_as_alphamind rm -f /opt/alphamind/src/out/secure/secure_data/test.tmp"

echo "🔍 Existing output files:"
if [ -d /opt/alphamind/src/out ]; then
    find /opt/alphamind/src/out -name "*.json" -type f | head -5 | while read -r file; do
        echo "  📄 $file ($(stat -c%s "$file") bytes)"
    done
else
    echo "  📁 No output directory yet"
fi
echo ""

echo "🧪 TEST EMISSIONS COLLECTION"
echo "============================"
if [ -f /opt/alphamind/venv/bin/activate ] && [ -d /opt/alphamind/src ]; then
    echo "🔍 Testing basic emissions collection (10 second timeout)..."
    if run_as_alphamind bash -c "cd /opt/alphamind/src && source /opt/alphamind/venv/bin/activate && timeout 10 python3 -c 'from emissions.snapshot import take_snapshot_map; print(f\"Test: {len(take_snapshot_map())} subnets found\")'" 2>&1; then
        echo "✅ Basic emissions collection test passed"
    else
        echo "❌ Basic emissions collection test failed"
    fi
else
    echo "❌ Cannot test - environment not ready"
fi
echo ""

echo "📝 LOG FILES CHECK"
echo "=================="
for log_file in "/var/log/alphamind-emissions.log" "/opt/alphamind/logs/emissions.log" "/opt/alphamind/src/nav_update.log"; do
    if [ -f "$log_file" ]; then
        echo "📄 $log_file ($(wc -l < "$log_file") lines)"
        echo "   Last entry: $(tail -1 "$log_file" 2>/dev/null | cut -c1-80)..."
    fi
done
echo ""

echo "🎯 RECOMMENDATIONS"
echo "=================="
echo "Based on the checks above, here are the next steps:"
echo ""

# Generate specific recommendations based on checks
if ! id alphamind &>/dev/null; then
    echo "1. 🚨 CRITICAL: Run the VPS setup script first:"
    echo "   sudo bash deployment/vps_complete_setup.sh"
elif ! run_as_alphamind bash -c "source /opt/alphamind/venv/bin/activate && which btcli" &>/dev/null; then
    echo "1. 🔧 Install btcli:"
    echo "   sudo -u alphamind bash -c 'source /opt/alphamind/venv/bin/activate && pip install bittensor btcli'"
elif ! run_as_alphamind bash -c "aws sts get-caller-identity" &>/dev/null; then
    echo "1. ☁️ Configure AWS credentials:"
    echo "   sudo -u alphamind aws configure"
    echo "   (Use your AWS Access Key ID and Secret Access Key)"
elif ! systemctl is-active alphamind-emissions.timer &>/dev/null; then
    echo "1. ⏰ Start the automation timer:"
    echo "   sudo systemctl start alphamind-emissions.timer"
    echo "   sudo systemctl status alphamind-emissions.timer"
else
    echo "1. ✅ System looks ready! Test manual collection:"
    echo "   sudo -u alphamind /opt/alphamind/run_daily.sh"
fi

echo ""
echo "2. 📊 Monitor the system:"
echo "   sudo systemctl status alphamind-emissions.timer"
echo "   sudo journalctl -u alphamind-emissions.service -f"
echo ""
echo "3. 🔍 Check logs regularly:"
echo "   sudo -u alphamind tail -f /opt/alphamind/src/out/emissions.log"
echo ""
echo "🎉 VPS diagnostic complete!"
