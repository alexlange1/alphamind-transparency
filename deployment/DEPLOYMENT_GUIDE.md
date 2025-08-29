# 🚀 AlphaMind VPS Deployment Guide

This guide walks you through deploying the secure, production-ready AlphaMind emissions collection system on a VPS with S3 storage and GitHub verification.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   VPS Server    │    │   AWS S3        │    │ GitHub Actions  │
│                 │    │                 │    │                 │
│ • btcli fetch   │───▶│ • Versioned     │───▶│ • Daily verify  │
│ • Crypto sign   │    │   storage       │    │ • Public badge  │
│ • Merkle tree   │    │ • Lifecycle     │    │ • Transparency  │
│ • systemd timer │    │ • Encryption    │    │ • Audit trail   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        ↓                        ↓                        ↓
   Secure Collection       Immutable Storage       Public Verification
```

## 📋 Prerequisites

### 1. **VPS Requirements**
- **OS**: Ubuntu 22.04 LTS
- **RAM**: 2GB minimum
- **Storage**: 20GB SSD
- **Network**: Outbound internet access
- **Providers**: DigitalOcean ($6/mo), Linode ($5/mo), Vultr ($6/mo)

### 2. **AWS S3 Setup**
- AWS account with S3 access
- S3 bucket with versioning enabled
- IAM user with S3 permissions
- Estimated cost: $1-2/month

### 3. **GitHub Repository**
- Your AlphaMind repository
- Optional: Separate transparency repository
- GitHub Actions enabled

## 🚀 Step-by-Step Deployment

### Step 1: Create VPS

**DigitalOcean Example:**
```bash
# Create droplet via CLI (or use web interface)
doctl compute droplet create alphamind-emissions \
    --image ubuntu-22-04-x64 \
    --size s-1vcpu-2gb \
    --region nyc3 \
    --ssh-keys YOUR_SSH_KEY_ID
```

### Step 2: Set Up AWS S3

```bash
# Create S3 bucket
aws s3 mb s3://alphamind-emissions-data --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket alphamind-emissions-data \
    --versioning-configuration Status=Enabled

# Create IAM user and policy
aws iam create-user --user-name alphamind-emissions

# Attach policy (see deployment/aws/s3-policy.json)
aws iam attach-user-policy \
    --user-name alphamind-emissions \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT:policy/AlphaMindS3Access

# Create access keys
aws iam create-access-key --user-name alphamind-emissions
```

### Step 3: Deploy to VPS

**SSH to your VPS and run:**

```bash
# Download and run setup script
curl -fsSL https://raw.githubusercontent.com/alexlange1/alphamind/bugbot/deployment/vps/setup_vps.sh | sudo bash

# The script will:
# ✅ Create alphamind user with secure permissions
# ✅ Install Python, btcli, and dependencies
# ✅ Set up systemd service and timer
# ✅ Configure firewall and security hardening
# ✅ Create directory structure with proper permissions
```

### Step 4: Configure Environment

**Switch to alphamind user and configure:**

```bash
sudo -u alphamind -i
cd /opt/alphamind

# Create environment configuration
cat > secrets/.env << EOF
# AWS S3 Configuration
S3_BUCKET=alphamind-emissions-data
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1

# AlphaMind Configuration
ALPHAMIND_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
BITTENSOR_NETWORK=finney

# Optional: Discord notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url

# Optional: Transparency repository
TRANSPARENCY_REPO=https://github.com/username/alphamind-transparency.git
TRANSPARENCY_BRANCH=main
EOF

chmod 600 secrets/.env
```

### Step 5: Test the System

```bash
# Test manual collection
sudo -u alphamind /opt/alphamind/deployment/vps/collect_and_upload.sh

# Check systemd service
sudo systemctl status alphamind-emissions.service

# Enable and start timer
sudo systemctl enable --now alphamind-emissions.timer

# Check timer status
sudo systemctl list-timers alphamind-emissions.timer
```

### Step 6: Set Up GitHub Verification

**Add secrets to your GitHub repository:**

Go to: `Repository → Settings → Secrets and variables → Actions`

Add these secrets:
```
VERIFY_AWS_ACCESS_KEY_ID=your_readonly_access_key
VERIFY_AWS_SECRET_ACCESS_KEY=your_readonly_secret_key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=alphamind-emissions-data
```

**The GitHub workflow will:**
- ✅ Run daily at 17:00 UTC (1 hour after collection)
- ✅ Download manifest and verify Ed25519 signature
- ✅ Verify Merkle tree integrity
- ✅ Generate public verification badge
- ✅ Create transparency reports

## 🔍 Monitoring & Maintenance

### **Daily Monitoring**

```bash
# Check collection status
journalctl -u alphamind-emissions.service --since today

# View recent logs
tail -f /opt/alphamind/logs/emissions_*.log

# Check S3 uploads
aws s3 ls s3://alphamind-emissions-data/emissions/$(date -u '+%Y/%m/%d')/

# Verify GitHub Actions
# Visit: https://github.com/username/alphamind/actions
```

### **System Health Checks**

```bash
# Check timer status
sudo systemctl status alphamind-emissions.timer

# View upcoming runs
sudo systemctl list-timers alphamind-emissions.timer

# Check disk space
df -h /opt/alphamind/

# Check memory usage
htop
```

### **Security Monitoring**

```bash
# Check firewall status
sudo ufw status verbose

# View failed login attempts
sudo journalctl -u fail2ban --since today

# Check file permissions
ls -la /opt/alphamind/secrets/
ls -la /opt/alphamind/data/secure/
```

## 🔧 Troubleshooting

### **Collection Fails**

```bash
# Check btcli connectivity
sudo -u alphamind btcli subnets list --network finney

# Test manual collection
sudo -u alphamind bash -c "cd /opt/alphamind && python3 scripts/daily_emissions_collection.py"

# Check environment variables
sudo -u alphamind bash -c "cd /opt/alphamind && source secrets/.env && env | grep -E '(S3_|AWS_|ALPHAMIND_)'"
```

### **S3 Upload Issues**

```bash
# Test S3 access
sudo -u alphamind aws s3 ls s3://alphamind-emissions-data/

# Check S3 permissions
aws s3api get-bucket-versioning --bucket alphamind-emissions-data

# Test upload manually
sudo -u alphamind bash /opt/alphamind/deployment/vps/s3_sync.sh
```

### **GitHub Verification Fails**

1. Check GitHub Actions logs for specific errors
2. Verify S3 bucket is publicly readable for manifests
3. Ensure AWS credentials in GitHub secrets are correct
4. Check if manifest exists in S3 for the verification date

## 💰 Cost Breakdown

| Component | Provider | Monthly Cost |
|-----------|----------|-------------|
| VPS (2GB RAM) | DigitalOcean | $6.00 |
| S3 Storage (10GB) | AWS | $0.23 |
| S3 Requests | AWS | $0.05 |
| Data Transfer | AWS | $0.09 |
| **Total** | | **~$6.37/month** |

## 🛡️ Security Features

✅ **System Hardening**
- Dedicated user with minimal privileges
- UFW firewall (outbound only)
- fail2ban SSH protection
- systemd security sandbox
- Secure file permissions (700/600)

✅ **Data Security**
- Ed25519 cryptographic signatures
- SHA-256 file hashing
- Merkle tree verification
- HMAC authentication
- S3 server-side encryption

✅ **Transparency**
- Public GitHub verification
- Signed manifests
- Immutable S3 versioning
- Complete audit trails

## 🎯 Production Checklist

Before going live, verify:

- [ ] VPS is properly secured and hardened
- [ ] S3 bucket has versioning enabled
- [ ] systemd timer is running (check with `systemctl list-timers`)
- [ ] Manual collection test succeeds
- [ ] S3 upload test succeeds
- [ ] GitHub verification workflow runs successfully
- [ ] Discord notifications work (if configured)
- [ ] Monitoring and alerting is set up
- [ ] Backup procedures are documented
- [ ] Access credentials are securely stored

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review system logs: `journalctl -u alphamind-emissions.service`
3. Verify all configuration in `secrets/.env`
4. Test each component individually
5. Check GitHub Actions logs for verification issues

**🎉 Once deployed, your AlphaMind subnet will have enterprise-grade, tamper-proof emissions data collection running 24/7!**
