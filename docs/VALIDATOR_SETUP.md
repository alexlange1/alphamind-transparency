# 🛡️ Alphamind Validator Setup Guide

Welcome to the Alphamind TAO20 subnet! This guide will help you set up and run a validator to earn rewards by operating the subnet infrastructure and ensuring data quality.

## 🎯 **What Do Validators Do?**

As an Alphamind validator, you are a **subnet operator** that:

- **📊 Aggregates Data**: Collect and process reports from miners
- **🧮 Computes Consensus**: Use stake-weighted algorithms to determine truth
- **⚖️ Scores Miners**: Evaluate miner performance and apply penalties
- **🏦 Simulates Vault**: Run TAO20 index calculations and NAV updates
- **🌐 Serves API**: Provide public endpoints for weights, prices, and dashboard
- **🔐 Publishes Proofs**: Submit on-chain evidence of weightset calculations

## 💰 **Earning Potential**

- **Subnet Operation Fees**: Earn from TAO20 transaction fees
- **Consensus Rewards**: Rewards for accurate data aggregation
- **API Usage Fees**: Optional revenue from premium API features
- **Validator Set Rewards**: Share of overall subnet incentives

## 🔧 **Requirements**

### **Hardware**
- **CPU**: 4+ cores (data processing and API serving)
- **RAM**: 8GB+ (consensus calculations and caching)
- **Storage**: 100GB+ (historical data and state management)
- **Network**: High-bandwidth, low-latency connection

### **Software**
- **Python**: 3.11+
- **Database**: PostgreSQL or SQLite for state management
- **Web Server**: Nginx or similar for production API
- **Monitoring**: Prometheus + Grafana recommended

### **Economic**
- **TAO Stake**: Higher stake required for validator registration
- **Operating Costs**: $50-200/month for reliable VPS hosting
- **Infrastructure**: Additional costs for monitoring and backups

## 🚀 **Quick Setup (10 minutes)**

### **Step 1: Clone and Install**
```bash
# Clone the repository
git clone https://github.com/alphamind/tao20-subnet.git
cd tao20-subnet

# Install dependencies (including API server)
pip install -r subnet/requirements.txt
pip install uvicorn[standard]

# Make CLI executable
chmod +x alphamind
```

### **Step 2: Configuration**
```bash
# Set environment variables
export AM_OUT_DIR=$(pwd)/data/validator
export AM_IN_DIR=$(pwd)/data/validator
export AM_API_TOKEN="your-secure-api-token"
export AM_WALLET="your-validator-wallet"
export AM_HOTKEY="your-validator-hotkey"

# Optional: Customize consensus parameters
export AM_EMISSIONS_QUORUM=0.33
export AM_PRICE_QUORUM=0.33
```

### **Step 3: Initialize Deployment**
```bash
# Initialize validator environment
./alphamind deploy init --network testnet

# Check system health
./alphamind deploy health
```

### **Step 4: Test Operations**
```bash
# Generate test data (simulate miner reports)
./alphamind demo --scenario aggregate

# Start validator API
./alphamind validator serve --host 0.0.0.0 --port 8000
```

### **Step 5: Verify Setup**
```bash
# Check API health
curl http://localhost:8000/healthz

# View dashboard
open http://localhost:8000/dashboard

# Test aggregation
curl -H "Authorization: Bearer your-api-token" \
     http://localhost:8000/aggregate
```

🎉 **You're now validating!** Your validator is processing data and serving the API.

## 🏗️ **Production Setup**

### **Using Templates**
```python
# Create production validator
from templates.validator_template import create_validator

validator = create_validator(
    validator_id="production-validator-001",
    in_dir="/data/alphamind/input",
    out_dir="/data/alphamind/output",
    top_n=20
)

# Run processing loop
await validator.run_continuous(interval=300)
```

### **Configuration File**
Create `validator_config.json`:
```json
{
  "validator_id": "validator-001",
  "network": "mainnet",
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "workers": 4
  },
  "consensus": {
    "emissions_quorum": 0.33,
    "price_quorum": 0.33,
    "staleness_threshold": 300
  },
  "scoring": {
    "penalty_threshold": 0.1,
    "slashing_enabled": true,
    "strike_limit": 3
  }
}
```

## 🐳 **Docker Deployment**

### **Single Container**
```bash
# Build validator image
docker build -f examples/docker/Dockerfile.validator -t alphamind-validator .

# Run validator container
docker run -d \
  --name my-alphamind-validator \
  -p 8000:8000 \
  -e AM_API_TOKEN="your-secure-token" \
  -e AM_WALLET="your-wallet" \
  -e AM_HOTKEY="your-hotkey" \
  -v $(pwd)/data:/alphamind/data \
  alphamind-validator
```

### **Full Production Stack**
```bash
# Use complete Docker Compose stack
cd examples/docker
docker-compose up -d

# Services included:
# - Validator API (port 8000)
# - Redis cache (port 6379)  
# - Prometheus metrics (port 9090)
# - Grafana dashboard (port 3000)
```

### **Kubernetes Deployment**
```yaml
# k8s/validator-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alphamind-validator
spec:
  replicas: 2
  selector:
    matchLabels:
      app: alphamind-validator
  template:
    metadata:
      labels:
        app: alphamind-validator
    spec:
      containers:
      - name: validator
        image: alphamind-validator:latest
        ports:
        - containerPort: 8000
        env:
        - name: AM_API_TOKEN
          valueFrom:
            secretKeyRef:
              name: alphamind-secrets
              key: api-token
```

## 📊 **Monitoring and Operations**

### **Health Monitoring**
```bash
# System health check
./alphamind deploy health

# API health endpoint
curl http://localhost:8000/healthz

# Detailed metrics
curl http://localhost:8000/metrics | jq
```

### **Performance Dashboards**
Access monitoring dashboards:
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **API Dashboard**: http://localhost:8000/dashboard

### **Log Management**
```bash
# View validator logs
docker logs alphamind-validator -f

# Structured logging
tail -f $AM_OUT_DIR/validator.log | jq

# Error monitoring
grep ERROR $AM_OUT_DIR/validator.log
```

## ⚖️ **Consensus and Scoring**

### **Understanding Consensus**
The validator uses **stake-weighted median consensus**:

1. **Collect Reports**: Gather signed reports from miners
2. **Validate Data**: Check signatures and basic sanity
3. **Apply Weights**: Weight by miner stake amounts
4. **Calculate Median**: Compute stake-weighted median values
5. **Detect Outliers**: Identify and penalize bad actors
6. **Publish Results**: Generate consensus weightset

### **Miner Scoring System**
```python
# Scoring parameters
SOFT_DEVIATION_THRESHOLD = 0.05  # 5%
HARD_DEVIATION_THRESHOLD = 0.10  # 10%
STRIKE_LIMIT = 3
SUSPENSION_DURATION = 24 * 60 * 60  # 24 hours
```

### **Penalty Structure**
| Violation | Penalty | Action |
|-----------|---------|--------|
| 5-10% deviation | 5% score reduction | Warning |
| >10% deviation | 20% score reduction + strike | Penalty |
| 3 strikes | Temporary suspension | Exclusion |
| Manipulation | Permanent slashing | Ban |

## 🌐 **API Configuration**

### **Endpoint Documentation**
Core API endpoints:
- `GET /healthz` - Health check
- `GET /weights` - Current index weights
- `GET /prices` - Latest consensus prices
- `GET /nav` - TAO20 Net Asset Value
- `POST /aggregate` - Trigger aggregation
- `GET /dashboard` - Web interface

### **Authentication**
```bash
# API key authentication
curl -H "Authorization: Bearer ${AM_API_TOKEN}" \
     http://localhost:8000/weights
```

### **Rate Limiting**
Default limits:
- **General**: 100 requests/minute
- **Minting**: 10 operations/5 minutes
- **Admin**: Unlimited (with proper auth)

### **CORS Configuration**
```bash
# Allow specific origins
export AM_CORS_ORIGINS="https://alphamind.xyz,https://dashboard.alphamind.xyz"
```

## 🔐 **Security Configuration**

### **Access Controls**
```bash
# Generate secure API token
export AM_API_TOKEN=$(openssl rand -hex 32)

# Restrict network access
# Run behind nginx/cloudflare
# Enable fail2ban for SSH
```

### **SSL/TLS Setup**
```nginx
# /etc/nginx/sites-available/alphamind
server {
    listen 443 ssl;
    server_name api.alphamind.xyz;
    
    ssl_certificate /etc/letsencrypt/live/api.alphamind.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.alphamind.xyz/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### **Backup Strategy**
```bash
# Automated backups
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf "/backups/alphamind_${DATE}.tar.gz" \
    $AM_OUT_DIR/weightset_*.json \
    $AM_OUT_DIR/vault_state.json \
    $AM_OUT_DIR/miner_scores.json

# Keep 30 days of backups
find /backups -name "alphamind_*.tar.gz" -mtime +30 -delete
```

## 📈 **Performance Optimization**

### **Caching Strategy**
```python
# Redis caching for API responses
import redis

cache = redis.Redis(host='localhost', port=6379, db=0)
cache.setex('weights:latest', 300, json.dumps(weights))  # 5-min cache
```

### **Database Optimization**
```sql
-- PostgreSQL indexes for faster queries
CREATE INDEX idx_reports_timestamp ON miner_reports(timestamp);
CREATE INDEX idx_scores_miner_id ON miner_scores(miner_id);
```

### **API Performance**
```python
# Async FastAPI with connection pooling
from fastapi import FastAPI
import asyncpg

app = FastAPI()

@app.on_event("startup")
async def startup():
    app.state.db_pool = await asyncpg.create_pool(
        "postgresql://user:pass@localhost/alphamind"
    )
```

## 🔄 **Consensus Algorithms**

### **Stake-Weighted Median**
```python
def stake_weighted_median(values, stakes):
    """
    Compute stake-weighted median for consensus
    """
    sorted_pairs = sorted(zip(values, stakes))
    total_stake = sum(stakes)
    cumulative_stake = 0
    
    for value, stake in sorted_pairs:
        cumulative_stake += stake
        if cumulative_stake >= total_stake / 2:
            return value
```

### **Outlier Detection**
```python
def detect_outliers(values, threshold=5.0):
    """
    Modified Z-Score outlier detection
    """
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    modified_z_scores = 0.6745 * (values - median) / mad
    return np.abs(modified_z_scores) > threshold
```

## 🐛 **Troubleshooting**

### **Common Issues**

**"API server won't start"**
```bash
# Check port availability
lsof -i :8000

# Try different port
./alphamind validator serve --port 8001
```

**"No miner reports found"**
```bash
# Check input directory
ls -la $AM_IN_DIR/

# Generate test data
./alphamind demo --scenario aggregate
```

**"Consensus failing"**
```bash
# Check quorum settings
echo $AM_EMISSIONS_QUORUM
echo $AM_PRICE_QUORUM

# Lower thresholds for testing
export AM_EMISSIONS_QUORUM=0.1
```

**"High memory usage"**
```bash
# Monitor memory
top -p $(pgrep -f alphamind)

# Check for memory leaks
valgrind python subnet/validator/api.py
```

### **Debug Mode**
```bash
# Run with debug logging
./alphamind validator serve --debug

# Check detailed logs
tail -f $AM_OUT_DIR/debug.log
```

## 📊 **Key Performance Indicators**

### **Validator Metrics**
- **Uptime**: Target >99.9%
- **Response Time**: API <100ms median
- **Consensus Success**: >95% successful aggregations
- **Miner Coverage**: Track active miner participation
- **Data Quality**: Monitor outlier detection rates

### **Business Metrics**
- **API Usage**: Track endpoint usage patterns
- **Fee Generation**: Monitor transaction fee collection
- **NAV Accuracy**: Compare with market prices
- **Index Performance**: Track TAO20 vs constituent performance

## 🆘 **Getting Help**

### **Resources**
- 📖 **Documentation**: [docs/](.)
- 🐛 **Issues**: [GitHub Issues](https://github.com/alphamind/issues)
- 💬 **Discord**: [Alphamind Community](https://discord.gg/alphamind)
- 📧 **Email**: validator-support@alphamind.xyz

### **Emergency Contacts**
- **Critical Issues**: emergency@alphamind.xyz
- **Security Issues**: security@alphamind.xyz
- **24/7 Support**: Available for major validators

## 🚀 **Advanced Topics**

### **High Availability Setup**
```bash
# Multi-region deployment
# Primary: us-east-1
# Secondary: eu-west-1
# Failover: asia-pacific-1
```

### **Load Balancing**
```nginx
upstream alphamind_validators {
    server validator1.alphamind.xyz:8000;
    server validator2.alphamind.xyz:8000;
    server validator3.alphamind.xyz:8000;
}
```

### **Custom Consensus Algorithms**
```python
# Implement custom consensus logic
from subnet.tao20.consensus import ConsensusEngine

class CustomConsensus(ConsensusEngine):
    def aggregate_emissions(self, reports):
        # Your custom logic here
        return custom_weighted_average(reports)
```

### **Smart Contract Integration**
```python
# Publish weightsets on-chain
from subnet.validator.publish import publish_weightset

await publish_weightset(
    weights=latest_weights,
    epoch_id=current_epoch,
    validator_address=validator_address
)
```

---

🎉 **Congratulations!** You're now ready to run a professional Alphamind validator. Start with the quick setup and scale to production as you gain experience.

**Happy Validating!** 🛡️
