# 🔐 AlphaMind Transparency Repository Deployment Guide

This guide sets up a dedicated, secure GitHub repository for publishing emissions data with minimal permissions.

## 🎯 Security Benefits

✅ **Isolated Repository**: Transparency data separate from main codebase  
✅ **Limited Token Scope**: Only `public_repo` permission  
✅ **Automated Publishing**: Daily updates without manual intervention  
✅ **Public Verification**: Anyone can verify emissions data  
✅ **Cryptographic Security**: Ed25519 signatures + SHA-256 integrity  

## 📋 Step-by-Step Setup

### 1. Create GitHub Personal Access Token

1. Go to: https://github.com/settings/personal-access-tokens/tokens
2. Click "Generate new token (classic)"
3. Configure:
   - **Note**: `AlphaMind-VPS-Emissions-Publisher`
   - **Expiration**: 1 year
   - **Scopes**: ✅ **ONLY** `public_repo` (uncheck everything else)
4. Click "Generate token"
5. **Copy and save the token securely**

### 2. Create Dedicated Repository

```bash
# On your local machine, run:
GITHUB_TOKEN=ghp_your_token_here bash setup_transparency_repo.sh
```

This will create: `https://github.com/alexlange1/alphamind-transparency`

### 3. Deploy to VPS

```bash
# Copy updated scripts to VPS
scp deployment/vps/update_transparency_dedicated.sh root@138.68.69.71:/opt/alphamind/src/deployment/vps/
scp deployment/vps/collect_and_upload.sh root@138.68.69.71:/opt/alphamind/src/deployment/vps/

# SSH to VPS
ssh root@138.68.69.71

# Set GitHub token in environment
echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> /opt/alphamind/secrets/.env
echo 'export TRANSPARENCY_REPO_URL="https://ghp_your_token_here@github.com/alexlange1/alphamind-transparency.git"' >> /opt/alphamind/secrets/.env

# Make scripts executable
chmod +x /opt/alphamind/src/deployment/vps/update_transparency_dedicated.sh
chmod +x /opt/alphamind/src/deployment/vps/collect_and_upload.sh
```

### 4. Test the Setup

```bash
# On VPS, test the transparency publishing
cd /opt/alphamind/src
source secrets/.env
bash deployment/vps/update_transparency_dedicated.sh
```

### 5. Verify Automatic Publishing

The transparency repository will be updated automatically during the next scheduled emissions collection (daily at 16:00 UTC).

## 📊 Repository Structure

The transparency repository will contain:

```
alphamind-transparency/
├── README.md                    # Live dashboard with latest stats
├── daily/                       # Daily emissions data
│   ├── emissions_20250907.json  # Raw subnet emissions
│   └── emissions_20250908.json
├── manifests/                   # Cryptographic verification
│   ├── manifest_20250907.json   # Signatures and merkle roots
│   └── manifest_20250908.json
└── status/                      # Collection metadata
    └── latest.json              # Current status and stats
```

## 🔍 Data Verification

Anyone can verify the emissions data:

1. **Check Signatures**: Verify Ed25519 signatures in manifests
2. **Validate Integrity**: Check SHA-256 + HMAC hashes
3. **Cross-Reference S3**: Compare with S3 bucket data
4. **Subnet Percentages**: Calculate percentage distributions

## 🚨 Security Notes

- **Token Scope**: Only `public_repo` - cannot access private repos or sensitive data
- **Repository Isolation**: Transparency data completely separate from main codebase
- **Public Verification**: All data publicly auditable
- **Automatic Rotation**: Consider rotating token annually

## 🔧 Troubleshooting

### Token Issues
```bash
# Test token permissions
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### Repository Issues
```bash
# Check repository access
git clone https://$GITHUB_TOKEN@github.com/alexlange1/alphamind-transparency.git /tmp/test
```

### VPS Issues
```bash
# Check logs
tail -f /opt/alphamind/src/logs/emissions_*.log
```

## 📈 Expected Results

After setup, you'll see:
- Daily commits to `alphamind-transparency` repository
- Real-time README with subnet statistics
- Cryptographically signed emissions data
- Public transparency dashboard

Repository URL: https://github.com/alexlange1/alphamind-transparency
