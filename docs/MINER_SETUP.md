# 🛠️ Alphamind Miner Setup Guide

Welcome to the Alphamind TAO20 subnet! This guide will help you set up and run a miner to earn rewards by providing accurate data about Bittensor subnet emissions and prices.

## 🎯 **What Do Miners Do?**

As an Alphamind miner, you are a **data oracle** that:

- **📊 Collects Emissions Data**: Monitor TAO emissions across all Bittensor subnets
- **💰 Fetches Price Data**: Get real-time prices from AMM pools and exchanges  
- **🧮 Calculates NAV**: Compute Net Asset Value for the TAO20 index
- **✍️ Signs Reports**: Submit cryptographically signed data reports
- **🏆 Earns Rewards**: Get rewarded based on data accuracy and timeliness

## 💰 **Earning Potential**

- **Accuracy Rewards**: Higher rewards for providing precise data
- **Timeliness Bonus**: Early submission bonuses
- **Consistency Multiplier**: Bonus for reliable, continuous operation
- **Stake Weighting**: Rewards proportional to your TAO stake

## 🔧 **Requirements**

### **Hardware**
- **CPU**: 2+ cores (lightweight data collection)
- **RAM**: 2GB+ (minimal memory usage)
- **Storage**: 10GB+ (for logs and cached data)
- **Network**: Stable internet connection

### **Software**
- **Python**: 3.11+ 
- **Bittensor**: `btcli` installation recommended
- **Git**: For repository management

### **Economic**
- **TAO Stake**: Minimum stake for miner registration (varies by subnet)
- **Operating Costs**: ~$5-20/month for VPS hosting

## 🚀 **Quick Setup (5 minutes)**

### **Step 1: Clone and Install**
```bash
# Clone the repository
git clone https://github.com/alphamind/tao20-subnet.git
cd tao20-subnet

# Install dependencies
pip install -r subnet/requirements.txt

# Make CLI executable
chmod +x alphamind
```

### **Step 2: Configuration**
```bash
# Set environment variables
export AM_OUT_DIR=$(pwd)/data/miner
export AM_MINER_SECRET="your-secure-secret"
export AM_WALLET="your-wallet-name"
export AM_HOTKEY="your-hotkey-name"

# Optional: Path to btcli
export AM_BTCLI="/path/to/btcli"
```

### **Step 3: Test Run**
```bash
# Test miner functionality
./alphamind miner emit-once --type both

# Check output
ls $AM_OUT_DIR/
# Should show: emissions_*.json, prices_*.json
```

### **Step 4: Start Mining**
```bash
# Run continuous miner (5-minute intervals)
./alphamind miner run --interval 300
```

🎉 **You're now mining!** Your miner will collect data and submit reports every 5 minutes.

## 🏗️ **Advanced Setup**

### **Using Templates**
```python
# Create custom miner using templates
from templates.miner_template import create_miner

miner = create_miner(
    miner_id="my-production-miner",
    interval=300,  # 5 minutes
    out_dir="/data/alphamind/miner"
)

# Run continuously
await miner.run_continuous()
```

### **Configuration File**
Create `miner_config.json`:
```json
{
  "miner_id": "my-miner-001",
  "interval": 300,
  "out_dir": "/data/alphamind",
  "btcli_path": "/usr/local/bin/btcli",
  "backup_enabled": true,
  "log_level": "INFO"
}
```

## 🐳 **Docker Deployment**

### **Single Container**
```bash
# Build miner image
docker build -f examples/docker/Dockerfile.miner -t alphamind-miner .

# Run miner container
docker run -d \
  --name my-alphamind-miner \
  -e AM_MINER_SECRET="your-secret" \
  -e AM_WALLET="your-wallet" \
  -e AM_HOTKEY="your-hotkey" \
  -v $(pwd)/data:/alphamind/data \
  alphamind-miner
```

### **Docker Compose**
```yaml
# docker-compose.yml
version: '3.8'
services:
  miner:
    build:
      context: .
      dockerfile: examples/docker/Dockerfile.miner
    environment:
      - AM_MINER_SECRET=your-secure-secret
      - AM_WALLET=your-wallet
      - AM_HOTKEY=your-hotkey
    volumes:
      - ./data:/alphamind/data
    restart: unless-stopped
```

```bash
# Start with compose
docker-compose up -d miner
```

## 📊 **Monitoring Your Miner**

### **Health Checks**
```bash
# Check miner health
./alphamind deploy health

# View recent reports
ls -la $AM_OUT_DIR/

# Check logs
tail -f $AM_OUT_DIR/miner.log
```

### **Performance Metrics**
```python
# Get miner performance
from templates.miner_template import create_miner

miner = create_miner("my-miner")
health = await miner.health_check()
print(health)
```

### **Web Dashboard**
If a validator is running locally:
```
http://localhost:8000/dashboard
```

## 🎯 **Optimization Tips**

### **Data Accuracy**
- **Sync btcli regularly**: Keep Bittensor client updated
- **Monitor network connectivity**: Ensure stable connection
- **Validate data locally**: Check reports before submission
- **Handle edge cases**: Graceful error handling for network issues

### **Performance**
- **Caching**: Cache price data to reduce API calls
- **Batching**: Submit multiple reports efficiently
- **Monitoring**: Track success rates and response times
- **Redundancy**: Run multiple miners for reliability

### **Stake Management**
- **Optimal stake size**: Balance rewards vs capital efficiency
- **Stake distribution**: Consider spreading across multiple hotkeys
- **Monitor validator selection**: Track which validators accept your reports

## 🔐 **Security Best Practices**

### **Key Management**
```bash
# Use secure secret generation
export AM_MINER_SECRET=$(openssl rand -hex 32)

# Protect wallet files
chmod 600 ~/.bittensor/wallets/*/hotkeys/*
```

### **Network Security**
- Run behind firewall
- Use VPN for additional privacy
- Monitor for unusual network activity
- Keep dependencies updated

### **Operational Security**
- Regular backups of configuration
- Monitor resource usage
- Set up alerting for downtime
- Use monitoring services

## 🐛 **Troubleshooting**

### **Common Issues**

**"No btcli found"**
```bash
# Install btcli
pip install bittensor

# Or specify path
export AM_BTCLI="/path/to/btcli"
```

**"Permission denied"**
```bash
# Fix permissions
chmod +x alphamind
chmod 755 data/
```

**"Connection timeout"**
```bash
# Check network connectivity
ping subtensor.network

# Test btcli connection
btcli subnets list
```

**"Reports not accepted"**
- Check data accuracy against other miners
- Verify stake amount meets minimum requirements
- Ensure reports are properly signed
- Check validator requirements and preferences

### **Debug Mode**
```bash
# Run with verbose logging
./alphamind miner emit-once --type both --debug

# Check detailed logs
tail -f $AM_OUT_DIR/debug.log
```

## 📈 **Performance Tracking**

### **Key Metrics to Monitor**
- **Report Success Rate**: Target >95%
- **Response Time**: Keep under 30 seconds
- **Data Accuracy**: Compare with consensus values
- **Uptime**: Aim for >99% availability
- **Validator Acceptance**: Track which validators use your data

### **Tools**
```bash
# Performance summary
./alphamind miner stats --days 7

# Compare with network
./alphamind miner compare --metric accuracy
```

## 🆘 **Getting Help**

### **Resources**
- 📖 **Documentation**: [docs/](.)
- 🐛 **Issues**: [GitHub Issues](https://github.com/alphamind/issues)
- 💬 **Discord**: [Alphamind Community](https://discord.gg/alphamind)
- 📧 **Email**: miner-support@alphamind.xyz

### **Community**
- Share configs and optimizations
- Report bugs and improvements
- Collaborate on best practices
- Get help with technical issues

## 🚀 **Advanced Topics**

### **High-Frequency Mining**
For advanced users wanting to run high-frequency data collection:
```python
# Sub-minute intervals
miner = create_miner("hf-miner", interval=30)  # 30 seconds
```

### **Multi-Subnet Mining**
Run miners for multiple subnets:
```bash
# Different configurations per subnet
./alphamind miner run --subnet 1 --config subnet1.json
./alphamind miner run --subnet 2 --config subnet2.json
```

### **Custom Data Sources**
Integrate additional data sources:
```python
# Custom price feeds
from subnet.tao20.price_feed import PriceFeed

custom_feed = PriceFeed(sources=["binance", "coinbase", "custom_api"])
```

---

🎉 **Congratulations!** You're now ready to run a profitable Alphamind miner. Start with the quick setup and gradually optimize based on performance metrics.

**Happy Mining!** ⛏️
