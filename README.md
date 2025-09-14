# TAO20 Index - Transparency Repository

## 🎯 **Overview**

This repository provides **complete transparency** for the TAO20 index fund - a top-20 emissions-weighted Bittensor subnet index. All data is collected directly from the Bittensor Finney network and published daily for full public verification.

## 📊 **What You'll Find Here**

### 🔄 **Daily Emissions Data** (`emissions/`)
- **Schedule**: Every day at 16:00 UTC
- **Source**: Live Bittensor Finney network via `btcli`
- **Format**: JSON files with complete subnet emission rates
- **Naming**: `emissions_YYYYMMDD.json`

### 📈 **TAO20 Index Composition** (`tao20/`)
- **Schedule**: Every second Sunday at 16:30 UTC (bi-weekly rebalancing)
- **Methodology**: 14-day rolling average of emissions, top 20 subnets
- **Format**: JSON files with complete index weights and metadata
- **Naming**: `tao20_YYYYMMDD.json`

## 🏗️ **Methodology**

### **Daily Data Collection**
1. **Real-time extraction** from Bittensor Finney network
2. **Subnet filtering**: Excludes subnet 0 (root network) and inactive subnets
3. **Complete metadata** including timestamps, total emissions, and network statistics
4. **Immediate publication** to GitHub with signed commits

### **TAO20 Index Calculation**
1. **14-day lookback**: Uses the most recent 14 daily emission snapshots
2. **Average calculation**: Computes mean emission rate for each subnet
3. **Top 20 selection**: Ranks subnets by average emissions and selects top 20
4. **Weight normalization**: Ensures total portfolio weight equals 100%
5. **Bi-weekly rebalancing**: Updates every second Sunday to maintain current market representation

## 📁 **Data Structure**

### **Daily Emissions Format**
```json
{
  "metadata": {
    "timestamp": "2025-09-14T16:00:00+00:00",
    "date": "20250914",
    "source": "bittensor_finney_network",
    "collection_method": "btcli_subnet_list_json",
    "network": "finney",
    "total_active_subnets": 118,
    "total_emission_rate": 0.999080
  },
  "emissions": {
    "1": 0.012400,
    "2": 0.008956,
    "64": 0.098466
  },
  "statistics": {
    "total_emission_rate": 0.999080,
    "avg_emission_rate": 0.008467,
    "max_emission_rate": 0.098466,
    "min_emission_rate": 0.000001,
    "active_subnets": 118
  }
}
```

### **TAO20 Index Format**
```json
{
  "metadata": {
    "index_name": "TAO20",
    "index_type": "Top-20 Emissions-Weighted Bittensor Subnet Index",
    "rebalance_date": "20250914",
    "generation_timestamp": "2025-09-14T16:30:00+00:00",
    "methodology": "14-day average emissions, top 20 subnets, normalized weights",
    "total_constituents": 20,
    "data_period_days": 14
  },
  "tao20_constituents": [
    {
      "rank": 1,
      "netuid": 64,
      "weight": 0.154900,
      "weight_percentage": 15.49,
      "avg_emission_rate": 0.098466
    }
  ]
}
```

## 🔍 **Verification & Transparency**

### **Data Integrity**
- **Source verification**: All data comes directly from Bittensor's Finney network
- **Real-time collection**: No manual intervention or data manipulation
- **Complete audit trail**: Every update is tracked via Git commits
- **Public accessibility**: All historical data is permanently accessible

### **Methodology Verification**
- **Open calculation**: Index weights are computed using simple arithmetic on public emissions data
- **Reproducible results**: Anyone can verify calculations using the provided emission snapshots
- **Historical tracking**: Complete history of all rebalancing decisions

### **Network Independence**
- **Direct blockchain access**: No reliance on third-party APIs or data providers
- **Automated collection**: Eliminates human bias or manual errors
- **Real-time publishing**: Data appears on GitHub within minutes of collection

## 📈 **Current Index Status**

Latest TAO20 composition can always be found in the most recent `tao20/tao20_YYYYMMDD.json` file.

**Key Statistics:**
- **Index Universe**: ~118 active Bittensor subnets
- **Selection Criteria**: Top 20 by 14-day average emissions
- **Rebalancing Frequency**: Bi-weekly (every 2nd Sunday)
- **Weight Distribution**: Market-cap weighted by emission rates

## 🌐 **Public Access**

### **GitHub Repository**
- **URL**: [github.com/alexlange1/alphamind-transparency](https://github.com/alexlange1/alphamind-transparency)
- **Access**: Public, read-only for transparency
- **Updates**: Automated daily and bi-weekly commits

### **Data Download**
All data files are directly accessible via GitHub:
- **Latest emissions**: Browse `emissions/` folder
- **Latest TAO20**: Browse `tao20/` folder
- **Historical data**: Use Git history to access previous versions
- **Raw file access**: Download individual JSON files directly

## 📱 **Programmatic Access**

### **REST API Access**
GitHub provides free API access to all repository data:

```bash
# Get latest emissions file
curl -s "https://api.github.com/repos/alexlange1/alphamind-transparency/contents/emissions" | \
  jq -r 'map(select(.name | contains("emissions_"))) | sort_by(.name) | last | .download_url'

# Get latest TAO20 composition
curl -s "https://api.github.com/repos/alexlange1/alphamind-transparency/contents/tao20" | \
  jq -r 'map(select(.name | contains("tao20_"))) | sort_by(.name) | last | .download_url'
```

### **Python Integration**
```python
import requests
import json
from datetime import datetime

# Fetch latest TAO20 composition
response = requests.get('https://api.github.com/repos/alexlange1/alphamind-transparency/contents/tao20')
files = response.json()
latest_tao20 = max([f for f in files if f['name'].startswith('tao20_')], key=lambda x: x['name'])

# Download and parse
data_response = requests.get(latest_tao20['download_url'])
tao20_data = data_response.json()

print(f"TAO20 Index as of {tao20_data['metadata']['rebalance_date']}")
for constituent in tao20_data['tao20_constituents'][:5]:
    print(f"#{constituent['rank']}: Subnet {constituent['netuid']} - {constituent['weight_percentage']:.2f}%")
```

## ❓ **FAQ**

### **How often is data updated?**
- **Emissions**: Daily at 16:00 UTC
- **TAO20 Index**: Bi-weekly (every 2nd Sunday) at 16:30 UTC

### **Can I trust this data?**
Yes - all data comes directly from the Bittensor blockchain with complete transparency:
- Source code and methodology are fully documented
- All collection is automated with no human intervention
- Complete Git history provides full audit trail
- Data can be independently verified against the Bittensor network

### **How do I get historical data?**
Use Git to browse historical versions:
```bash
git clone https://github.com/alexlange1/alphamind-transparency.git
cd alphamind-transparency
git log --oneline  # See all historical updates
git checkout <commit-hash>  # View data at specific point in time
```

### **What if I find an error?**
The system is designed to eliminate human error through automation, but if you notice any issues:
1. **Cross-reference** with direct Bittensor network queries
2. **Check Git history** for any unusual commits
3. **Contact us** via GitHub issues for investigation

## 📞 **Contact & Support**

- **Issues**: [GitHub Issues](https://github.com/alexlange1/alphamind-transparency/issues)
- **Documentation**: This README and embedded JSON metadata
- **Updates**: Watch this repository for notifications

---

## 🏷️ **Latest Update**

**Last Data Collection**: Check the latest file timestamps in `emissions/` and `tao20/` folders  
**System Status**: Fully automated and operational  
**Next Rebalancing**: Every second Sunday at 16:30 UTC  

*This repository represents AlphaMind's commitment to complete transparency in TAO20 index fund management.*