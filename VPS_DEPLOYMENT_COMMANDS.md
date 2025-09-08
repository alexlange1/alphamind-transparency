# VPS Deployment Commands for GitHub Sync

## Quick Deployment (Automated)

Run the automated deployment script:
```bash
bash deployment/deploy_github_sync_to_vps.sh
```

## Manual Deployment Steps

If you prefer to deploy manually, run these commands:

### 1. SSH to VPS
```bash
ssh root@138.68.69.71
```

### 2. Switch to alphamind user and update code
```bash
sudo -u alphamind -i
cd /opt/alphamind
git pull origin main
chmod +x deployment/vps/github_sync.sh
```

### 3. Create emissions-data directory structure
```bash
mkdir -p emissions-data/daily
mkdir -p emissions-data/secure  
mkdir -p emissions-data/manifests
```

### 4. Configure Git for automated commits
```bash
git config --global user.name "AlphaMind VPS Bot"
git config --global user.email "alphamind-vps@alexlange.dev"
```

### 5. Install GitHub CLI (for automated PRs)
```bash
# As root user
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh -y
```

### 6. Test the new system
```bash
# Switch back to alphamind user
sudo -u alphamind -i
cd /opt/alphamind

# Test GitHub sync (dry run)
bash deployment/vps/github_sync.sh
```

### 7. Restart services
```bash
# As root
sudo systemctl restart alphamind-emissions.service
sudo systemctl status alphamind-emissions.service
sudo systemctl list-timers alphamind-emissions.timer
```

## What Changed

1. **New GitHub Sync**: Emissions data now uploads to GitHub instead of S3
2. **Automatic PRs**: Creates pull requests for data transparency  
3. **Directory Structure**: Creates `emissions-data/` folder with organized structure
4. **Backup Option**: S3 upload is now optional (set `ENABLE_S3_BACKUP=true` if needed)

## Next Collection

The next automated collection at 16:00 UTC will:
- ✅ Collect emissions data as usual
- ✅ Upload to GitHub in `emissions-data-updates` branch
- ✅ Create a pull request for transparency
- ✅ Make data publicly available at: https://github.com/alexlange1/alphamind

## Verification

After deployment, verify with:
```bash
# Check if GitHub sync script exists and is executable
ls -la deployment/vps/github_sync.sh

# Check service status
sudo systemctl status alphamind-emissions.service
sudo systemctl status alphamind-emissions.timer

# View next scheduled run
sudo systemctl list-timers alphamind-emissions.timer
```

## Troubleshooting

If issues occur:
1. Check service logs: `sudo journalctl -u alphamind-emissions.service -f`
2. Test manual collection: `sudo -u alphamind bash deployment/vps/collect_and_upload.sh`
3. Test GitHub sync: `sudo -u alphamind bash deployment/vps/github_sync.sh`
