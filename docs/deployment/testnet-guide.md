# 🧪 TAO20 Testnet Deployment Guide

## 🎯 **Stealth Testnet Deployment**

This guide will help you deploy TAO20 to BEVM testnet while maintaining maximum privacy and security.

## 🔒 **Privacy-First Approach**

### **🕵️ Stealth Mode Features**
- ✅ **No Source Verification**: Contract bytecode only (unreadable)
- ✅ **Obfuscated Functions**: Function names appear as hashes
- ✅ **Private Testing**: Test functionality without public scrutiny
- ✅ **Competitive Advantage**: Keep innovation secret until ready
- ✅ **Flexible Reveal**: Verify source code later when desired

---

## 📋 **Prerequisites**

### **🛠️ Required Tools**
```bash
✅ Foundry (forge, cast, anvil)
✅ Git and GitHub access
✅ BEVM testnet BTC (from faucet)
✅ Text editor
✅ Terminal/command line
```

### **🔐 Wallet Preparation**
You should already have production wallets from the previous setup:
```bash
Deployer Wallet: 0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29
Seed Phrase: wild fruit parade health strong raise funny dust rotate zone scout dentist
```

---

## 💰 **Funding Your Testnet Wallet**

### **Step 1: Get Testnet TAO**

**Bittensor EVM Testnet requires TAO for gas fees. Request testnet TAO via:**

**Method 1: Bittensor Community Discord**
- Join the official Bittensor Discord
- Request testnet TAO in the developer channel
- Provide your address: `0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29`

**Method 2: BTCLI Live Coding Playground**
- Access the BTCLI playground environment
- Use built-in testnet funding tools

**Method 3: Community Request Template**
```
Hi! I'm developing TAO20 on Bittensor EVM testnet.
EVM Address: 0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29
Network: Chain ID 945
Purpose: Smart contract testing
Amount: 1-2 testnet TAO
```

### **Step 2: Verify Balance**
```bash
cast balance 0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29 \
  --rpc-url https://test.chain.opentensor.ai
```

**Minimum Required**: 0.1 TAO for deployment
**Recommended**: 0.5 TAO for safety margin

---

## 🔧 **Environment Setup**

### **Step 1: Configure Stealth Environment**
```bash
cd /Users/alexanderlange/alphamind
cp deployment/testnet/config/stealth.env.example deployment/testnet/config/stealth.env
```

### **Step 2: Edit Configuration**
```bash
nano deployment/testnet/config/stealth.env
```

Add your settings:
```bash
# 🕵️ TAO20 Stealth Testnet Configuration
TESTNET_PRIVATE_KEY=19299f620e8d00e88ec5e48ab48ed4d53c1a0c674909c1e52b427194b7b2519d
TESTNET_RPC_URL=https://test.chain.opentensor.ai
TESTNET_CHAIN_ID=945

# Privacy Settings
ENABLE_SOURCE_VERIFICATION=false
USE_GENERIC_NAMES=true
DEPLOYMENT_MODE=stealth
```

### **Step 3: Secure the Configuration**
```bash
chmod 600 deployment/testnet/config/stealth.env
```

---

## 🚀 **Stealth Deployment Process**

### **Method 1: Automated Stealth Script (Recommended)**
```bash
cd /Users/alexanderlange/alphamind
./deployment/testnet/deploy-stealth.sh
```

**What This Does:**
- ✅ Validates wallet balance
- ✅ Deploys all contracts WITHOUT source verification
- ✅ Saves contract addresses privately
- ✅ Maintains maximum privacy
- ✅ Provides clear next steps

### **Method 2: Manual Deployment**
```bash
cd /Users/alexanderlange/alphamind/core/contracts

# Load environment
source ../../deployment/testnet/config/stealth.env

# Deploy without verification (stealth mode)
forge script script/DeployLocalTest.s.sol \
  --rpc-url $TESTNET_RPC_URL \
  --private-key $TESTNET_PRIVATE_KEY \
  --broadcast \
  --legacy \
  --slow
  # Note: NO --verify flag = stealth mode!
```

---

## 📊 **Post-Deployment Verification**

### **Step 1: Extract Contract Addresses**
```bash
cd core/contracts
cat broadcast/DeployLocalTest.s.sol/1501/run-latest.json | jq '.transactions[] | select(.contractAddress != null) | {name: .contractName, address: .contractAddress}'
```

### **Step 2: Verify Deployment Success**
```bash
# Check TAO20 Core contract
cast code <TAO20_CORE_ADDRESS> --rpc-url https://testnet-rpc.bevm.io

# Should return long bytecode string (not 0x)
```

### **Step 3: Test Basic Functionality**
```bash
# Check if contracts are responding
cast call <TAO20_CORE_ADDRESS> "getCurrentNAV()" --rpc-url https://test.chain.opentensor.ai

# Should return a number (NAV in wei)
```

---

## 🔍 **Privacy Verification**

### **Step 1: Check Block Explorer**
Visit: https://test.chain.opentensor.ai/address/<CONTRACT_ADDRESS> (if block explorer available)

**What You Should See:**
- ✅ Contract address exists
- ✅ Bytecode is present but unreadable
- ✅ No source code tab
- ✅ Functions appear as hashes (0xa9059cbb...)
- ✅ No obvious connection to TAO20

### **Step 2: Verify Privacy Level**
```bash
# This should show unreadable bytecode
curl -s "https://scan-testnet.bevm.io/api/contract/<CONTRACT_ADDRESS>" | jq '.sourceCode'

# Should return null or empty - good!
```

---

## 🧪 **Private Testing Phase**

### **Step 1: Update Python Configuration**
Edit `core/neurons/test_real_contracts.py` to use testnet addresses:
```python
DEPLOYED_ADDRESSES = {
    "TAO20Core": "0x<TESTNET_CORE_ADDRESS>",
    "TAO20Token": "0x<TESTNET_TOKEN_ADDRESS>", 
    "Vault": "0x<TESTNET_VAULT_ADDRESS>",
    # ... etc
}
```

### **Step 2: Test Real Integration**
```bash
cd core/neurons
python test_real_contracts.py
```

**Expected Results:**
- ✅ All 6 tests should pass
- ✅ Real BEVM precompile integration
- ✅ Actual cross-chain functionality
- ✅ Live contract interaction

### **Step 3: Validate Core Functions**
```bash
# Test NAV calculation
cast call <TAO20_CORE_ADDRESS> "getCurrentNAV()" --rpc-url https://testnet-rpc.bevm.io

# Test vault configuration  
cast call <VAULT_ADDRESS> "getSupportedSubnets()" --rpc-url https://testnet-rpc.bevm.io

# Test token supply
cast call <TOKEN_ADDRESS> "totalSupply()" --rpc-url https://testnet-rpc.bevm.io
```

---

## 🔧 **Troubleshooting**

### **Common Issues & Solutions**

#### **❌ "Insufficient Balance" Error**
```bash
# Check balance
cast balance 0xEb762Ce2c1268362feDFAEFDe5eE32Cc5351FA29 --rpc-url https://testnet-rpc.bevm.io

# Get more testnet BTC from faucet
# Wait 24 hours between faucet requests
```

#### **❌ "RPC Connection Failed"**
```bash
# Test RPC connectivity
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  https://testnet-rpc.bevm.io

# Try alternative RPC if needed
```

#### **❌ "Contract Not Found"**
```bash
# Verify contract was deployed
cast code <CONTRACT_ADDRESS> --rpc-url https://testnet-rpc.bevm.io

# If returns 0x, deployment failed
# Check broadcast logs for errors
```

#### **❌ "Private Key Invalid"**
```bash
# Verify private key format
echo $TESTNET_PRIVATE_KEY | wc -c
# Should be 66 characters (including 0x prefix)

# Test key with cast
cast wallet address $TESTNET_PRIVATE_KEY
```

---

## 📊 **Monitoring Your Deployment**

### **Contract Activity Monitoring**
```bash
# Monitor transactions
cast logs --from-block latest --address <CONTRACT_ADDRESS> --rpc-url https://testnet-rpc.bevm.io

# Check gas usage
cast tx <DEPLOYMENT_TX_HASH> --rpc-url https://testnet-rpc.bevm.io
```

### **Performance Metrics**
- **Deployment Cost**: Track total gas used
- **Function Response**: Measure call response times
- **Integration Health**: Monitor Python test results
- **Privacy Status**: Verify no source code leaks

---

## 🎯 **Next Steps After Deployment**

### **Phase 1: Private Validation (1-2 weeks)**
1. **Comprehensive Testing**: Test all functions thoroughly
2. **Integration Validation**: Verify Python ↔ Contract communication
3. **Performance Monitoring**: Track gas costs and response times
4. **Security Review**: Internal security assessment
5. **Documentation**: Record any issues or improvements

### **Phase 2: Trusted Testing (1 week)**
1. **Limited Disclosure**: Share with 2-3 trusted advisors
2. **External Security Review**: Professional security audit
3. **Feedback Integration**: Implement suggested improvements
4. **Final Validation**: Confirm everything works perfectly

### **Phase 3: Source Code Reveal (When Ready)**
```bash
# Verify source code when ready for public review
forge verify-contract <CONTRACT_ADDRESS> TAO20CoreV2OracleFree \
  --rpc-url https://testnet-rpc.bevm.io \
  --constructor-args $(cast abi-encode "constructor(address,address,string,string)" <NAV_CALC> <VAULT> "TAO20 Index Token" "TAO20")
```

---

## 🏆 **Success Metrics**

### **Deployment Success Indicators**
- ✅ All contracts deployed without errors
- ✅ Contract bytecode exists at all addresses
- ✅ No source code visible on block explorer
- ✅ Basic functions respond correctly
- ✅ Python integration tests pass
- ✅ Cross-chain functionality works

### **Privacy Success Indicators**
- ✅ No obvious TAO20 branding visible
- ✅ Function names obfuscated
- ✅ Purpose unclear to casual observers
- ✅ No media attention or discovery
- ✅ Competitive advantage maintained

---

## 🎉 **Congratulations!**

If you've successfully completed this guide, you now have:

- ✅ **Working TAO20 system** deployed to BEVM testnet
- ✅ **Maximum privacy** maintained during testing phase
- ✅ **Real integration validation** with BEVM precompiles
- ✅ **Professional deployment** ready for production
- ✅ **Competitive advantage** preserved until public launch

**You're now ready to test the real TAO20 system privately and perfect it before the public launch!** 🚀

---

**Need Help?** Contact the development team or check the [troubleshooting guide](troubleshooting.md) for additional support.
