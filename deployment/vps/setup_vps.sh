#!/bin/bash
set -euo pipefail

# AlphaMind VPS Setup Script
# Run this on a fresh Ubuntu 22.04 LTS VPS as root

echo "🚀 Setting up AlphaMind Emissions Collection VPS"
echo "================================================"

# Update system
apt-get update && apt-get upgrade -y

# Install required packages
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    unzip \
    awscli \
    fail2ban \
    ufw \
    htop \
    jq

# Create dedicated alphamind user
useradd -m -s /bin/bash -G sudo alphamind
echo "alphamind:$(openssl rand -base64 32)" | chpasswd

# Set up secure umask for alphamind user
echo "umask 077" >> /home/alphamind/.bashrc
echo "umask 077" >> /home/alphamind/.profile

# Create project directory
mkdir -p /opt/alphamind
chown alphamind:alphamind /opt/alphamind
chmod 700 /opt/alphamind

# Switch to alphamind user for the rest of setup
sudo -u alphamind bash << 'EOF'
cd /opt/alphamind

# Clone the repository
git clone https://github.com/alexlange1/alphamind.git .
git checkout bugbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install bittensor-cli

# Create necessary directories with secure permissions
mkdir -p {data,logs,secrets,manifests}
chmod 700 {data,logs,secrets,manifests}

# Create secure directories for emissions data
mkdir -p data/secure/{secure_data,backups,integrity}
chmod 700 data/secure data/secure/*

# Test btcli installation
btcli --help > /dev/null && echo "✅ btcli installed successfully"

echo "✅ AlphaMind user setup completed"
EOF

# Set up firewall (outbound only for security)
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw --force enable

# Configure fail2ban for SSH protection
systemctl enable fail2ban
systemctl start fail2ban

# Create systemd service and timer files
cat > /etc/systemd/system/alphamind-emissions.service << 'EOF'
[Unit]
Description=AlphaMind Emissions Collection
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=alphamind
Group=alphamind
WorkingDirectory=/opt/alphamind
Environment=PATH=/opt/alphamind/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/opt/alphamind
ExecStart=/opt/alphamind/deployment/vps/collect_and_upload.sh
StandardOutput=journal
StandardError=journal
PrivateTmp=yes
NoNewPrivileges=yes
UMask=077

# Security hardening
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/alphamind/data /opt/alphamind/logs /opt/alphamind/manifests
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictRealtime=yes
RestrictNamespaces=yes
LockPersonality=yes
MemoryDenyWriteExecute=yes
RestrictAddressFamilies=AF_INET AF_INET6
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/alphamind-emissions.timer << 'EOF'
[Unit]
Description=Run AlphaMind Emissions Collection Daily
Requires=alphamind-emissions.service

[Timer]
# Run daily at 16:00 UTC (4 PM UTC)
OnCalendar=*-*-* 16:00:00
# Run missed jobs after system restart
Persistent=true
# Add random delay to avoid thundering herd
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

# Set proper permissions on systemd files
chmod 644 /etc/systemd/system/alphamind-emissions.{service,timer}

# Create log rotation config
cat > /etc/logrotate.d/alphamind << 'EOF'
/opt/alphamind/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 600 alphamind alphamind
}
EOF

echo "✅ VPS setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Configure AWS credentials: sudo -u alphamind aws configure"
echo "2. Set environment variables in /opt/alphamind/secrets/.env"
echo "3. Enable and start the timer: systemctl enable --now alphamind-emissions.timer"
echo "4. Check status: systemctl status alphamind-emissions.timer"
echo ""
echo "🔐 Security features enabled:"
echo "  • Dedicated alphamind user with restricted permissions"
echo "  • UFW firewall (outbound only)"
echo "  • fail2ban SSH protection"
echo "  • systemd security hardening"
echo "  • Secure umask (077) for all files"
echo ""
echo "📊 Monitor with:"
echo "  • journalctl -u alphamind-emissions.service -f"
echo "  • systemctl list-timers alphamind-emissions.timer"
