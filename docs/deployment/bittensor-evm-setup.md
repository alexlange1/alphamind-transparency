# 🔗 Bittensor EVM Network Setup Guide

## 🎯 **Bittensor EVM Architecture**

Bittensor EVM is the Ethereum-compatible execution layer built on top of the Bittensor network, enabling smart contract deployment while maintaining direct access to Bittensor's native features through precompiles.

---

## 🌐 **Network Configurations**

### **🧪 Bittensor EVM Testnet (Official)**

```bash
Network Name: Bittensor EVM Testnet
RPC URL: https://test.chain.opentensor.ai
Chain ID: 945
Currency Symbol: TAO
Block Explorer: https://test.chain.opentensor.ai (if available)
```

### **🚀 Bittensor EVM Mainnet**

```bash
Network Name: Bittensor EVM Mainnet
RPC URL: https://api-bittensor-mainnet.n.dwellir.com/YOUR_API_KEY
Chain ID: 945
Currency Symbol: TAO
WebSocket: wss://api-bittensor-mainnet.n.dwellir.com/YOUR_API_KEY
```

**Note**: Mainnet requires a Dwellir API key. Sign up at [dwellir.com](https://dwellir.com) for scalable RPC access.

---

## 🦊 **MetaMask Setup**

### **Add Bittensor EVM Testnet**

1. **Open MetaMask** and click on the network dropdown
2. **Select "Add Network"** or "Custom RPC"
3. **Enter the following details**:
   ```
   Network Name: Bittensor EVM Testnet
   New RPC URL: https://test.chain.opentensor.ai
   Chain ID: 945
   Currency Symbol: TAO
   Block Explorer URL: https://test.chain.opentensor.ai
   ```
4. **Save** and switch to the network

### **Add Bittensor EVM Mainnet**

1. **Get Dwellir API Key** from [dwellir.com](https://dwellir.com)
2. **Add Network** with details:
   ```
   Network Name: Bittensor EVM Mainnet
   New RPC URL: https://api-bittensor-mainnet.n.dwellir.com/YOUR_API_KEY
   Chain ID: 945
   Currency Symbol: TAO
   ```
3. **Save** and switch to the network

---

## 💰 **Getting Testnet TAO**

### **🎯 Testnet Funding Methods**

**Method 1: Bittensor Community Discord**
- Join the official Bittensor Discord
- Request testnet TAO in the appropriate channel
- Provide your EVM address: `0xYourAddress`

**Method 2: BTCLI Live Coding Playground**
- Access the BTCLI playground environment
- Use built-in testnet funding tools
- Transfer to your EVM address

**Method 3: Community Requests**
- Engage with the Bittensor community
- Request testnet TAO for development purposes
- Specify that you need EVM testnet TAO (Chain ID 945)

### **📋 Funding Request Template**

```
Hi! I'm developing a TAO20 index token project on Bittensor EVM.
I need testnet TAO for smart contract deployment testing.

EVM Address: 0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29
Network: Bittensor EVM Testnet (Chain ID 945)
Purpose: Smart contract deployment and testing
Amount Needed: ~1-2 testnet TAO

Thank you!
```

---

## 🔧 **Development Setup**

### **Environment Configuration**

Create your local environment file:
```bash
# Copy the template
cp deployment/testnet/config/stealth.env.example deployment/testnet/config/stealth.env

# Edit with your details
nano deployment/testnet/config/stealth.env
```

**Required Settings**:
```bash
TESTNET_PRIVATE_KEY=19299f620e8d00e88ec5e48ab48ed4d53c1a0c674909c1e52b427194b7b2519d
TESTNET_RPC_URL=https://test.chain.opentensor.ai
TESTNET_CHAIN_ID=945
```

### **Network Connectivity Test**

```bash
# Test RPC connectivity
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  https://test.chain.opentensor.ai

# Should return current block number
```

### **Wallet Balance Check**

```bash
# Check your testnet TAO balance
cast balance 0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29 \
  --rpc-url https://test.chain.opentensor.ai

# Convert to readable format
cast to-unit $(cast balance 0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29 \
  --rpc-url https://test.chain.opentensor.ai) ether
```

---

## ⚠️ **Important Notes**

### **🔍 Network Confusion**

**Correct Network**: 
- **Chain ID 945** with **TAO** as gas token
- **Official Bittensor EVM** as documented

**Avoid Confusion With**:
- Chain ID 11503 with BTC (different/unofficial variant)
- Other "BEVM" networks that aren't Bittensor's official EVM

### **🔐 Security Considerations**

**Testnet Security**:
- Use separate keys for testnet
- Never use mainnet private keys on testnet
- Testnet TAO has no real value

**Mainnet Security**:
- Use hardware wallets for significant funds
- Secure your Dwellir API key
- Monitor transactions carefully

### **💡 Best Practices**

**Development Workflow**:
1. Test extensively on testnet (Chain ID 945)
2. Validate all precompile integrations
3. Verify cross-chain functionality
4. Conduct security audits
5. Deploy to mainnet with monitoring

---

## 🚀 **Quick Start Commands**

### **Test Network Connection**
```bash
# Test connectivity
curl https://test.chain.opentensor.ai \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# Expected response: {"jsonrpc":"2.0","id":1,"result":"0x3b1"}
# (0x3b1 = 945 in decimal)
```

### **Deploy to Testnet**
```bash
# Configure environment
cp deployment/testnet/config/stealth.env.example deployment/testnet/config/stealth.env
nano deployment/testnet/config/stealth.env

# Deploy stealthily
./deployment/testnet/deploy-stealth.sh
```

### **Monitor Deployment**
```bash
# Check deployment status
cast tx $TX_HASH --rpc-url https://test.chain.opentensor.ai

# Check contract code
cast code $CONTRACT_ADDRESS --rpc-url https://test.chain.opentensor.ai
```

---

## 📚 **Additional Resources**

### **Official Documentation**
- [Bittensor Docs](https://docs.bittensor.com/)
- [Bittensor EVM Guide](https://docs.bittensor.com/evm/)
- [Dwellir RPC Provider](https://dwellir.com)

### **Community**
- [Bittensor Discord](https://discord.gg/bittensor)
- [Bittensor GitHub](https://github.com/opentensor)
- [Developer Resources](https://docs.bittensor.com/developers/)

### **Development Tools**
- [Foundry](https://getfoundry.sh/) - Smart contract development
- [Cast](https://book.getfoundry.sh/cast/) - Command-line tool
- [Anvil](https://book.getfoundry.sh/anvil/) - Local development

---

## ✅ **Verification Checklist**

Before deploying to mainnet, ensure:

- [ ] **Testnet thoroughly tested** on Chain ID 945
- [ ] **All precompiles working** with real Bittensor features
- [ ] **Cross-chain functionality validated**
- [ ] **Gas estimation accurate** for TAO-based fees
- [ ] **Security audit completed**
- [ ] **Monitoring systems ready**
- [ ] **Emergency procedures documented**

**You're now ready to deploy TAO20 on the official Bittensor EVM!** 🎉
