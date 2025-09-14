# TAO20 CPS - GitHub Transparency System

Complete transparency system for TAO20 index fund with GitHub as the only canonical storage.

## 🏗️ Architecture

- **Daily Emissions**: Collected at 16:00 UTC with ±5min jitter
- **Bi-weekly Rebalancing**: Every 2nd Sunday at 16:30 UTC  
- **Storage**: GitHub repository only (no S3)
- **Verification**: SHA256 checksums for all files
- **Notifications**: Discord webhooks for success/failure alerts

## 📁 Repository Structure

```
tao20-cps/
├── scripts/
│   ├── fetch_emissions.py   # Daily emissions collection
│   ├── compute_tao20.py     # Bi-weekly rebalancing
│   └── utils.py             # GitHub, Discord, checksum utilities
├── emissions/               # Daily JSON/CSV snapshots
├── tao20/                   # Bi-weekly compositions
├── logs/                    # Cron output logs
├── config.yaml              # Configuration template
├── env.example              # Environment variables template
└── README.md
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone repository
git clone https://github.com/alexlange1/alphamind-transparency.git
cd alphamind-transparency

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp env.example .env
# Edit .env with your tokens
```

### 2. Configure Secrets

Edit `.env` file:

```bash
# Required
GITHUB_TOKEN=your_github_personal_access_token_here
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here

# Optional overrides
REPO_PATH=.
EMISSIONS_LOOKBACK_DAYS=14
TAO20_TOP_N=20
```

### 3. Setup Cron Jobs

```bash
# Edit crontab
crontab -e

# Add these lines:
# Daily emissions @ 16:00 UTC (jitter inside script)
0 16 * * * cd /path/to/tao20-cps && /usr/bin/python3 scripts/fetch_emissions.py >> logs/emissions.log 2>&1

# TAO20 rebalance every 2nd Sunday @ 16:30 UTC
30 16 */14 * 0 cd /path/to/tao20-cps && /usr/bin/python3 scripts/compute_tao20.py >> logs/tao20.log 2>&1
```

## 📊 Data Formats

### Daily Emissions (`emissions/`)

**JSON Format:**
```json
{
  "timestamp": "2025-09-14T16:00:00+00:00",
  "date": "20250914",
  "total_subnets": 129,
  "emissions": {
    "0": 1.0,
    "1": 0.0124,
    "64": 0.0986
  },
  "total_emission_rate": 0.9995,
  "avg_emission_rate": 0.0321,
  "collection_method": "btcli_subnet_list",
  "network": "finney"
}
```

**CSV Format:**
```csv
netuid,emission_rate,emission_percentage
0,1.000000,100.0000
1,0.012400,1.2400
64,0.098600,9.8600
```

### TAO20 Index (`tao20/`)

**JSON Format:**
```json
{
  "metadata": {
    "index_name": "TAO20",
    "rebalance_date": "20250914",
    "methodology": "14-day average emissions, top 20 subnets",
    "total_constituents": 20
  },
  "tao20_constituents": [
    {
      "rank": 1,
      "netuid": 64,
      "weight": 0.1551,
      "weight_percentage": 15.51,
      "avg_emission_rate": 0.0986
    }
  ]
}
```

## 🔐 Security Features

- **SHA256 Checksums**: Every file has a `.sha256` checksum file
- **Git Signing**: Commits are signed with bot identity
- **Branch Protection**: Main branch protected from direct pushes
- **Audit Trail**: Complete git history for all changes
- **Verification**: All data can be independently verified

## 🔍 Verification

### Verify File Integrity
```bash
# Check if file matches its checksum
python3 -c "
from scripts.utils import ChecksumManager
from pathlib import Path
print(ChecksumManager.verify_checksum(Path('emissions/emissions_20250914.json')))
"
```

### Manual Data Collection
```bash
# Test emissions collection
python3 scripts/fetch_emissions.py

# Test TAO20 computation
python3 scripts/compute_tao20.py
```

## 📈 Monitoring

### Check System Status
```bash
# View recent logs
tail -f logs/emissions.log
tail -f logs/tao20.log

# Check cron jobs
crontab -l

# Verify recent commits
git log --oneline -10
```

### Discord Notifications

The system sends Discord notifications for:
- ✅ Daily emissions collection success
- ❌ Collection failures
- 🎯 TAO20 rebalancing completion
- ❌ Rebalancing failures

## 🛠️ Development

### Local Testing
```bash
# Test with sample data
python3 scripts/fetch_emissions.py
python3 scripts/compute_tao20.py

# Run with debug output
PYTHONPATH=. python3 -v scripts/fetch_emissions.py
```

### Adding New Features
1. Modify scripts in `scripts/`
2. Update utilities in `scripts/utils.py`
3. Test with sample data
4. Update documentation

## 📋 Troubleshooting

### Common Issues

**btcli not found:**
```bash
pip install bittensor-cli
```

**GitHub authentication failed:**
- Check `GITHUB_TOKEN` in `.env`
- Ensure token has `repo` permissions

**Discord notifications not working:**
- Verify `DISCORD_WEBHOOK_URL` in `.env`
- Test webhook URL manually

**Cron jobs not running:**
- Check cron service: `systemctl status cron`
- Verify file paths in crontab
- Check logs: `tail -f logs/emissions.log`

## 📄 License

MIT License - see LICENSE file for details.

---

**Last Updated:** 2025-09-14  
**Version:** 1.0.0  
**Maintainer:** AlphaMind Team