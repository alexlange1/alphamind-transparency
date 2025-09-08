# 🚀 Alphamind TAO20 Setup Guide

## 📋 **Prerequisites**

### **System Requirements**
- **Python**: 3.10+ (3.10.x recommended)
- **Memory**: 8GB+ RAM recommended
- **Storage**: 50GB+ available space
- **Network**: Stable internet connection

### **Required Accounts**
- **Bittensor Wallet**: Configured with sufficient TAO for operations
- **WandB Account**: For monitoring and analytics (optional but recommended)
- **EVM Wallet**: For TAO20 minting operations

## 🛠️ **Installation**

### **1. Clone Repository**
```bash
git clone https://github.com/yourusername/alphamind.git
cd alphamind
```

### **2. Python Environment Setup**
```bash
# Create virtual environment
python -m venv venv

# Activate environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### **3. Environment Configuration**
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### **4. Environment Variables**
```bash
# Bittensor Configuration
BITTENSOR_NETWORK=finney
TAO20_NETUID=20

# TAO20 Configuration
TAO20_API_URL=https://api.alphamind.ai
TAO20_EVM_ADDR=0xYourEVMAddressHere

# Optional: EVM Integration
BEVM_RPC_URL=https://rpc.bevm.io

# Optional: Disable WandB
WANDB_MODE=disabled
```

## 🔧 **Configuration**

### **Bittensor Wallet Setup**
```bash
# Create new wallet (if needed)
btcli wallet new_coldkey --wallet.name default
btcli wallet new_hotkey --wallet.name default --wallet.hotkey default

# Register on subnet (if not already registered)
btcli subnet register --netuid 20 --wallet.name default --wallet.hotkey default
```

### **WandB Setup (Recommended)**
```bash
# Install WandB
pip install wandb

# Login to WandB
wandb login

# Your API key will be saved automatically
```

## 🚀 **Running Nodes**

### **Running a Miner**
```bash
# Basic miner setup
python neurons/miner.py \
    --netuid 20 \
    --tao20.evm_addr 0xYourEVMAddressHere \
    --tao20.api_url https://api.alphamind.ai \
    --min_creation_size 1000

# Advanced configuration
python neurons/miner.py \
    --netuid 20 \
    --wallet.name your_wallet \
    --wallet.hotkey your_hotkey \
    --tao20.evm_addr 0xYourEVMAddressHere \
    --tao20.api_url https://api.alphamind.ai \
    --min_creation_size 1000 \
    --creation_interval 30 \
    --log_level DEBUG \
    --wandb.project alphamind-production
```

### **Running a Validator**
```bash
# Basic validator setup
python neurons/validator.py \
    --netuid 20 \
    --tao20.api_url https://api.alphamind.ai

# Advanced configuration
python neurons/validator.py \
    --netuid 20 \
    --wallet.name your_wallet \
    --wallet.hotkey your_hotkey \
    --tao20.api_url https://api.alphamind.ai \
    --min_attestation_interval 30 \
    --max_creation_age 1800 \
    --monitoring_interval 15 \
    --log_level INFO \
    --wandb.project alphamind-production
```

### **Dry Run Mode**
```bash
# Test without actual operations
python neurons/miner.py \
    --netuid 20 \
    --tao20.evm_addr 0xYourEVMAddressHere \
    --dry_run
```

## 📊 **Monitoring**

### **WandB Dashboard**
- Visit: https://wandb.ai/project/alphamind-tao20
- View real-time metrics, logs, and system health
- Compare performance across different nodes

### **Local Metrics**
```bash
# Check node health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics
```

### **Log Files**
```bash
# View recent logs
tail -f logs/miner.log
tail -f logs/validator.log

# Search for errors
grep ERROR logs/*.log
```

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Wallet Connection Issues**
```bash
# Check wallet status
btcli wallet overview --wallet.name default

# Verify network connection
btcli subnet list

# Check registration
btcli subnet list --netuid 20
```

#### **API Connection Issues**
```bash
# Test API connectivity
curl https://api.alphamind.ai/health

# Check environment variables
echo $TAO20_API_URL
echo $TAO20_EVM_ADDR
```

#### **Memory Issues**
```bash
# Monitor memory usage
htop

# Reduce batch sizes in configuration
export TAO20_MAX_BATCH_SIZE=10
```

#### **Network Issues**
```bash
# Check internet connectivity
ping 8.8.8.8

# Test subnet connectivity
btcli subnet metagraph --netuid 20
```

### **Performance Optimization**

#### **Miner Optimization**
```bash
# Increase creation frequency
--creation_interval 15

# Optimize for high volume
--min_creation_size 500

# Use faster acquisition strategy
--acquisition_strategy otc
```

#### **Validator Optimization**
```bash
# Reduce attestation interval
--min_attestation_interval 30

# Increase monitoring frequency
--monitoring_interval 10

# Process more creations in parallel
--max_concurrent_processing 5
```

## 📈 **Production Deployment**

### **Systemd Service (Linux)**
```bash
# Create service file
sudo nano /etc/systemd/system/tao20-miner.service
```

```ini
[Unit]
Description=TAO20 Miner
After=network.target

[Service]
Type=simple
User=tao20
WorkingDirectory=/home/tao20/alphamind
Environment=PATH=/home/tao20/alphamind/venv/bin
ExecStart=/home/tao20/alphamind/venv/bin/python neurons/miner.py --netuid 20 --tao20.evm_addr YOUR_EVM_ADDR
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable tao20-miner
sudo systemctl start tao20-miner
sudo systemctl status tao20-miner
```

### **Docker Deployment**
```bash
# Build image
docker build -t alphamind-tao20 .

# Run miner
docker run -d \
    --name tao20-miner \
    -e TAO20_EVM_ADDR=0xYourAddress \
    -v ~/.bittensor:/root/.bittensor \
    alphamind-tao20 \
    python neurons/miner.py --netuid 20
```

### **Monitoring Stack**
```bash
# Prometheus configuration
docker run -d \
    --name prometheus \
    -p 9090:9090 \
    prom/prometheus

# Grafana dashboard
docker run -d \
    --name grafana \
    -p 3000:3000 \
    grafana/grafana
```

## 🎯 **Next Steps**

1. **Join Community**: Connect with other operators on Discord/Telegram
2. **Monitor Performance**: Track your node's performance on WandB
3. **Optimize Strategy**: Adjust parameters based on network conditions
4. **Scale Operations**: Consider running multiple miners/validators
5. **Stay Updated**: Follow development updates and network upgrades

## 🆘 **Support**

- **Documentation**: Check `/docs` folder for detailed guides
- **Issues**: Report bugs on GitHub
- **Community**: Join Discord for real-time support
- **Email**: support@alphamind.ai

## 🔐 **Security Notes**

- **Never share** your private keys or wallet seeds
- **Use separate wallets** for different environments (testnet/mainnet)
- **Monitor logs** for suspicious activity
- **Keep software updated** with latest security patches
- **Use firewall** to restrict unnecessary network access

---

🎉 **Congratulations!** You're now ready to participate in the TAO20 subnet as either a miner or validator. Monitor your performance and optimize your strategy based on network conditions.
