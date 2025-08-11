# 📚 Alphamind Documentation

Welcome to the comprehensive documentation for the Alphamind TAO20 subnet! This directory contains all the guides and specifications you need to understand, deploy, and operate the subnet.

## 🚀 **Getting Started**

### **New to Alphamind?**
Start here to understand what the subnet does and get running quickly:

1. **[Quick Start Guide](QUICKSTART.md)** - Get up and running in 5 minutes
2. **[Protocol Overview](PROTOCOL_V1.md)** - Understand the technical specification
3. **Choose your role**: [Validator Setup](VALIDATOR_SETUP.md) or [Miner Setup](MINER_SETUP.md)

### **What is Alphamind?**
Alphamind is a **decentralized ETF subnet** that:
- 📊 Creates the **TAO20 Index** - top 20 Bittensor subnets by emissions
- 🔄 **Automatically rebalances** every 2 weeks based on performance
- 💰 Enables **minting/redemption** of TAO20 tokens at real-time NAV
- 🛡️ Uses **decentralized oracles** for price and emissions data
- 🏦 Operates like a **professional ETF** with transparent fees

## 👥 **Role-Specific Guides**

### **🛡️ For Validators (Subnet Operators)**
Validators operate the subnet infrastructure and earn fees:

- **[Complete Validator Setup](VALIDATOR_SETUP.md)** - Production deployment guide
- **[Security Best Practices](SECURITY_GUIDE.md)** - Secure your validator
- **[Production Deployment](DEPLOYMENT_SECURITY.md)** - Enterprise-grade deployment

**What Validators Do:**
- Aggregate data from miners using consensus algorithms
- Calculate index weights and serve public API
- Score miner performance and apply penalties
- Earn fees from TAO20 operations (0.2% + 1% annual)

### **⛏️ For Miners (Data Oracles)**
Miners provide accurate data and earn rewards:

- **[Complete Miner Setup](MINER_SETUP.md)** - Start mining in minutes
- **[Mining Best Practices](MINER_SETUP.md#optimization-tips)** - Optimize performance
- **[Troubleshooting](MINER_SETUP.md#troubleshooting)** - Common issues and solutions

**What Miners Do:**
- Monitor Bittensor network for emissions data
- Fetch real-time prices from AMM pools
- Submit signed reports for validator consensus
- Earn rewards based on accuracy and timeliness

## 🔧 **Technical Documentation**

### **Core Specifications**
- **[Protocol V1 Specification](PROTOCOL_V1.md)** - Complete technical protocol
- **[API Documentation](API.md)** - REST API endpoints and schemas
- **[Security Architecture](SECURITY_GUIDE.md)** - Multi-layer security framework

### **Smart Contracts**
- **[Contract Documentation](../contracts/README.md)** - Solidity contract details
- **[Deployment Guide](DEPLOYMENT_SECURITY.md)** - Contract deployment procedures

### **Architecture**
- **[System Architecture](PROTOCOL_V1.md#subnet-overview)** - High-level system design
- **[Consensus Algorithms](VALIDATOR_SETUP.md#consensus-algorithms)** - Stake-weighted median consensus
- **[Scoring System](VALIDATOR_SETUP.md#consensus-and-scoring)** - Miner performance evaluation

## 🛠️ **Operations Guides**

### **Deployment & Management**
- **[Production Deployment](DEPLOYMENT_SECURITY.md)** - Secure deployment procedures
- **[Monitoring & Alerting](VALIDATOR_SETUP.md#monitoring-and-operations)** - Observability setup
- **[Backup & Recovery](VALIDATOR_SETUP.md#security-configuration)** - Data protection

### **Security**
- **[Security Guide](SECURITY_GUIDE.md)** - Comprehensive security measures
- **[Access Controls](SECURITY_GUIDE.md)** - Authentication and authorization
- **[Incident Response](SECURITY_GUIDE.md)** - Emergency procedures

### **Performance**
- **[Optimization Guide](VALIDATOR_SETUP.md#performance-optimization)** - Performance tuning
- **[Scaling Strategies](VALIDATOR_SETUP.md#advanced-topics)** - High availability setup
- **[Monitoring KPIs](VALIDATOR_SETUP.md#key-performance-indicators)** - Key metrics to track

## 📊 **Business & Economics**

### **Tokenomics**
- **Index Composition**: Top 20 subnets by 14-day average emissions
- **Rebalancing**: Automatic every 2 weeks
- **Fees**: 0.2% transaction + 1% annual management
- **Rewards**: Distributed based on stake and performance

### **Market Mechanics**
- **Minting**: TAO → TAO20 tokens at current NAV
- **Redemption**: TAO20 → underlying assets (in-kind)
- **Price Discovery**: Decentralized oracle network
- **Liquidity**: AMM integration for efficient trading

## 🎯 **Use Cases**

### **For Investors**
- **Diversification**: Exposure to top-performing subnets
- **Professional Management**: Automated rebalancing and fee structure
- **Transparency**: On-chain proofs and real-time reporting
- **Liquidity**: Easy entry/exit through minting/redemption

### **For Subnet Operators**
- **Objective Ranking**: Merit-based inclusion in index
- **Capital Allocation**: Automatic funding to top performers
- **Market Infrastructure**: Professional index product
- **Network Effect**: Increased visibility and adoption

### **For Ecosystem**
- **Price Discovery**: Efficient subnet token pricing
- **Capital Flow**: Directing funds to productive subnets
- **Infrastructure**: Foundation for additional financial products
- **Standards**: Professional asset management practices

## 🔗 **Quick Links**

### **Essential Resources**
- 🚀 **[Quick Start](QUICKSTART.md)** - Get running immediately
- 🛡️ **[Validator Guide](VALIDATOR_SETUP.md)** - Earn fees operating infrastructure
- ⛏️ **[Miner Guide](MINER_SETUP.md)** - Earn rewards providing data
- 🔒 **[Security](SECURITY_GUIDE.md)** - Protect your operation

### **Developer Resources**
- 📋 **[Templates](../templates/)** - Quick start templates
- 💡 **[Examples](../examples/)** - Working examples
- 🐳 **[Docker](../examples/docker/)** - Containerized deployment
- 🧪 **[Tests](../tests/)** - Test suites and validation

### **Community & Support**
- 💬 **Discord**: [Alphamind Community](https://discord.gg/alphamind)
- 🐛 **Issues**: [GitHub Issues](https://github.com/alphamind/issues)
- 📧 **Email**: support@alphamind.xyz
- 🌐 **Website**: [alphamind.xyz](https://alphamind.xyz)

## 📈 **Performance Metrics**

Track these key metrics for successful operation:

| Role | Success Metrics | Target Values |
|------|----------------|---------------|
| **Validators** | Uptime, API response time, consensus success | >99.9%, <100ms, >95% |
| **Miners** | Report accuracy, submission rate, penalty avoidance | >95%, >98%, <5% |
| **System** | NAV accuracy, fee collection, index tracking | <1% error, 100%, <2% tracking |

## 🎓 **Learning Path**

### **Beginner** (30 minutes)
1. Read [Quick Start](QUICKSTART.md)
2. Run `./alphamind demo --scenario full`
3. Explore the dashboard at http://localhost:8000/dashboard

### **Intermediate** (2 hours)
1. Choose your role: [Validator](VALIDATOR_SETUP.md) or [Miner](MINER_SETUP.md)
2. Complete the setup guide for your chosen role
3. Deploy using Docker containers

### **Advanced** (1 day)
1. Study [Protocol Specification](PROTOCOL_V1.md)
2. Implement custom templates or integrations
3. Set up production monitoring and security

### **Expert** (Ongoing)
1. Contribute to protocol development
2. Optimize performance and security
3. Build additional tools and integrations

---

## 📝 **Documentation Standards**

This documentation follows these principles:
- **User-Focused**: Written for operators, not just developers
- **Action-Oriented**: Clear steps and examples
- **Comprehensive**: Covers setup through production
- **Up-to-Date**: Maintained with each release
- **Accessible**: Clear language and structure

## 🤝 **Contributing**

Help improve this documentation:
1. **Report Issues**: Found something unclear? [Open an issue](https://github.com/alphamind/issues)
2. **Suggest Improvements**: Have ideas? [Start a discussion](https://github.com/alphamind/discussions)
3. **Submit Changes**: [Pull requests welcome](https://github.com/alphamind/pulls)

---

**Ready to get started?** Begin with the [Quick Start Guide](QUICKSTART.md) and choose your path! 🚀
