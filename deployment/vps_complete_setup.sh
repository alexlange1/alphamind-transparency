#!/bin/bash
set -euo pipefail

# Complete AlphaMind VPS Setup Script
# Run this as root on Ubuntu 22.04 LTS

echo "🚀 AlphaMind VPS Complete Setup"
echo "=============================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root"
    echo "   Run: sudo bash vps_complete_setup.sh"
    exit 1
fi

echo "📋 Step 1: Creating alphamind user..."

# Create alphamind user
adduser --disabled-password --gecos "" alphamind
usermod -aG sudo alphamind
passwd -l alphamind

echo "🔥 Step 2: Setting up firewall..."

# Set up firewall
ufw allow OpenSSH
ufw --force enable
timedatectl set-timezone UTC

echo "🔐 Step 3: Creating security keys..."

# Create secure config directory
mkdir -p /etc/alphamind && chmod 700 /etc/alphamind

# Generate security keys
openssl rand -base64 32 > /etc/alphamind/hmac_v2.b64
ssh-keygen -t ed25519 -N '' -f /etc/alphamind/ed25519_manifest

# Create basic config
cat >/etc/alphamind/env <<'EOF'
S3_BUCKET=alphamind-emissions-data
S3_PREFIX=emissions
DISCORD_WEBHOOK_URL=
EOF
chmod 600 /etc/alphamind/env

echo "🐍 Step 4: Setting up Python environment..."

# Switch to alphamind user for setup
sudo -u alphamind bash << 'ALPHAMIND_SETUP'
cd ~

# Create Python virtual environment
python3 -m venv /opt/alphamind/venv

# Create directories
mkdir -p /opt/alphamind/src

# Clone repository
git clone https://github.com/alexlange1/alphamind /opt/alphamind/src
cd /opt/alphamind/src

# Switch to bugbot branch
git checkout bugbot

# Activate virtual environment and install dependencies
source /opt/alphamind/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install bittensor btcli cryptography boto3

echo "✅ Python environment setup completed"
ALPHAMIND_SETUP

echo "📝 Step 5: Creating daily runner script..."

# Create the daily runner script
sudo -u alphamind bash << 'RUNNER_SETUP'
cat >/opt/alphamind/run_daily.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
umask 077

# Load configuration
source /etc/alphamind/env

# Load HMAC key for data integrity
export ALPHAMIND_SECRET_KEY_B64="$(cat /etc/alphamind/hmac_v2.b64)"

# Activate Python environment
source /opt/alphamind/venv/bin/activate
cd /opt/alphamind/src

TODAY="$(date -u +%F)"
echo "🚀 Starting AlphaMind emissions collection for ${TODAY}"

# Create output directory
mkdir -p out/secure/secure_data

# Run emissions collection
python3 scripts/daily_emissions_collection.py

# Upload to S3
echo "☁️  Uploading to S3..."
aws s3 sync out/secure/ "s3://${S3_BUCKET}/${S3_PREFIX}/${TODAY}/" --exact-timestamps

# Create success marker
aws s3 cp /dev/null "s3://${S3_BUCKET}/${S3_PREFIX}/${TODAY}/_SUCCESS"

echo "✅ Done: ${TODAY}"
EOF

chmod +x /opt/alphamind/run_daily.sh
echo "✅ Runner script created"
RUNNER_SETUP

echo "⏰ Step 6: Setting up systemd automation..."

# Create systemd service
cat >/etc/systemd/system/alphamind-emissions.service <<'EOF'
[Unit]
Description=AlphaMind daily emissions collection
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=alphamind
EnvironmentFile=/etc/alphamind/env
ExecStart=/bin/bash -lc '/opt/alphamind/run_daily.sh'

[Install]
WantedBy=multi-user.target
EOF

# Create systemd timer
cat >/etc/systemd/system/alphamind-emissions.timer <<'EOF'
[Unit]
Description=Run AlphaMind emissions at 16:00 UTC daily

[Timer]
OnCalendar=*-*-* 16:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable the timer
systemctl daemon-reload
systemctl enable alphamind-emissions.timer

echo ""
echo "🎉 SETUP COMPLETED SUCCESSFULLY!"
echo "================================"
echo ""
echo "📋 What was configured:"
echo "  ✅ alphamind user created with secure permissions"
echo "  ✅ Firewall enabled (SSH only)"
echo "  ✅ Security keys generated"
echo "  ✅ Python environment with btcli installed"
echo "  ✅ AlphaMind repository cloned (bugbot branch)"
echo "  ✅ Daily automation configured (4 PM UTC)"
echo ""
echo "🔑 NEXT STEPS (REQUIRED):"
echo "1. Configure AWS credentials:"
echo "   sudo -u alphamind aws configure"
echo ""
echo "2. Test the system:"
echo "   sudo -u alphamind /opt/alphamind/run_daily.sh"
echo ""
echo "3. Start the timer:"
echo "   systemctl start alphamind-emissions.timer"
echo ""
echo "4. Check timer status:"
echo "   systemctl list-timers | grep alphamind"
echo ""
echo "🎯 After AWS configuration, your system will run automatically!"
echo "   Data will be collected daily at 4 PM UTC and stored in S3."
