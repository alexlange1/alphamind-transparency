# Alphamind Quick Start Guide

Welcome to Alphamind! This guide will get you up and running with the TAO20 subnet in minutes.

## 🚀 Quick Installation

### Prerequisites
- Python 3.11+
- Git
- Optional: Docker for containerized deployment

### 1. Clone and Setup
```bash
git clone https://github.com/alphamind/tao20-subnet.git
cd tao20-subnet

# Install dependencies
pip install -r subnet/requirements.txt

# Make CLI executable
chmod +x alphamind
```

### 2. Initialize Environment
```bash
# Initialize deployment
./alphamind deploy init --network testnet

# Check system health
./alphamind deploy health
```

## 🧪 Quick Demo

### Option A: Full Demo (Recommended)
```bash
# Run complete demonstration
./alphamind demo --scenario full
```

### Option B: Step by Step

**Step 1: Generate Sample Data**
```bash
# Emit miner reports
./alphamind miner emit-once --type both
```

**Step 2: Aggregate Reports**
```bash
# Process reports into index weights
./alphamind validator aggregate
```

**Step 3: Simulate Vault Operations**
```bash
# Simulate minting 100 TAO
./alphamind vault mint --amount 100.0

# Check vault status
./alphamind vault status
```

**Step 4: Start API Server**
```bash
# Start the validator API
./alphamind validator serve --host 0.0.0.0 --port 8000
```

**Step 5: View Dashboard**
```
Open: http://localhost:8000/dashboard
```

## 📊 Understanding the Output

### Miner Reports
- **Emissions Report**: TAO emissions per subnet over 14 days
- **Price Report**: Current prices from AMM pools

### Validator Aggregation
- **Weights**: Top 20 subnets by emissions (normalized)
- **Eligibility**: 90-day continuity requirements
- **Consensus**: Stake-weighted median values

### Vault Simulation
- **NAV**: Net Asset Value per TAO20 token
- **Holdings**: Proportional holdings of each subnet token
- **Fees**: Transaction (0.2%) and management (1% APR) fees

## 🔧 Configuration

### Environment Variables
```bash
# Required
export AM_OUT_DIR=/path/to/output
export AM_API_TOKEN=your-secure-token

# Optional
export AM_BTCLI=/path/to/btcli
export AM_WALLET=your-wallet
export AM_HOTKEY=your-hotkey
```

### Configuration File
```json
{
  "network": "testnet",
  "settings": {
    "emissions_quorum": 0.33,
    "price_quorum": 0.33,
    "top_n_subnets": 20,
    "tx_fee_bps": 20,
    "mgmt_fee_bps": 100
  }
}
```

## 🐳 Docker Deployment

### Single Container
```bash
# Build and run validator
docker build -f examples/docker/Dockerfile.validator -t alphamind-validator .
docker run -p 8000:8000 alphamind-validator
```

### Full Stack
```bash
# Run complete stack with monitoring
cd examples/docker
docker-compose up -d

# View services
docker-compose ps
```

## 🔍 Monitoring & Health

### Health Checks
```bash
# System health
./alphamind deploy health

# API health
curl http://localhost:8000/healthz

# Detailed metrics
curl http://localhost:8000/metrics | jq
```

### Log Files
- Miner reports: `$AM_OUT_DIR/emissions_*.json`, `$AM_OUT_DIR/prices_*.json`
- Aggregated weights: `$AM_OUT_DIR/weightset_latest.json`
- Vault state: `$AM_OUT_DIR/vault_state.json`

## 🛠️ Development Setup

### Using Templates
```python
# Miner template
from templates.miner_template import create_miner
miner = create_miner("my-miner")
await miner.run_once()

# Validator template
from templates.validator_template import create_validator
validator = create_validator("my-validator")
await validator.run_once()
```

### Custom Implementation
```python
# See examples/miners/basic_miner.py
# See examples/validators/basic_validator.py
```

## ⚡ Performance Tips

1. **Concurrent Operations**: Use async templates for better performance
2. **Caching**: Enable Redis for price/emissions caching
3. **Monitoring**: Use Prometheus + Grafana for observability
4. **Scaling**: Deploy multiple miners across different regions

## 🔒 Security Considerations

- Use secure API tokens in production
- Enable hotkey signing for miners
- Run behind reverse proxy (nginx/traefik)
- Monitor for unusual activity
- Keep dependencies updated

## 📚 Next Steps

### **Choose Your Role**
- **🛡️ Become a Validator**: [VALIDATOR_SETUP.md](VALIDATOR_SETUP.md) - Earn fees by operating subnet infrastructure
- **⛏️ Become a Miner**: [MINER_SETUP.md](MINER_SETUP.md) - Earn rewards by providing accurate data

### **Learn More**
- **📖 Protocol Specification**: [PROTOCOL_V1.md](PROTOCOL_V1.md)
- **🔒 Security Guide**: [SECURITY_GUIDE.md](SECURITY_GUIDE.md)
- **🚀 Production Deployment**: [DEPLOYMENT_SECURITY.md](DEPLOYMENT_SECURITY.md)
- **💼 Smart Contracts**: [contracts/README.md](../contracts/README.md)

### **Get Involved**
- **💬 Join Discord**: [Alphamind Community](https://discord.gg/alphamind)
- **🐛 Report Issues**: [GitHub Issues](https://github.com/alphamind/issues)
- **📧 Contact Us**: support@alphamind.xyz

## 🆘 Troubleshooting

### Common Issues

**"Command not found: alphamind"**
```bash
chmod +x alphamind
export PATH=$PATH:$(pwd)
```

**"API server not starting"**
```bash
# Check if port is in use
lsof -i :8000

# Try different port
./alphamind validator serve --port 8001
```

**"No reports found"**
```bash
# Check btcli installation
which btcli

# Run with demo data
./alphamind demo --scenario full
```

### Getting Help

- 📖 Documentation: [docs/](.)
- 🐛 Issues: [GitHub Issues](https://github.com/alphamind/issues)
- 💬 Discord: [Alphamind Community](https://discord.gg/alphamind)
- 📧 Email: support@alphamind.xyz

---

🎉 **Congratulations!** You're now running Alphamind TAO20 subnet. Happy indexing!
