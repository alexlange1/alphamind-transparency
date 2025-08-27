# 🏗️ Alphamind TAO20 Project Structure

## 📁 **Directory Organization**

```
alphamind/
├── 🧠 alphamind/                   # Core package
│   └── __init__.py                 # Package initialization
├── 🚀 neurons/                     # Bittensor neurons (main entry points)
│   ├── miner/                      # Miner implementation
│   │   ├── __init__.py
│   │   └── miner.py               # TAO20 miner logic
│   ├── validator/                  # Validator implementation
│   │   ├── __init__.py
│   │   ├── validator.py           # TAO20 validator logic
│   │   ├── nav_calculator.py      # NAV calculation engine
│   │   ├── incentive_manager.py   # Sophisticated reward system
│   │   └── enhanced_validator.py  # Enhanced validator features
│   ├── miner.py                   # Miner entry point with CLI
│   └── validator.py               # Validator entry point with CLI
├── 🔗 creation/                    # Creation unit system
│   ├── __init__.py
│   ├── epoch_manager.py           # Epoch and creation file management
│   ├── basket_validator.py        # Basket validation logic
│   ├── request_manager.py         # Creation request handling
│   └── epoch_enforcer.py          # Epoch boundary enforcement
├── 🔧 common/                      # Shared utilities
│   ├── __init__.py
│   ├── logging.py                 # Professional logging with WandB
│   ├── precompiles.py            # Bittensor precompile integration
│   ├── monitoring.py             # System monitoring
│   ├── rate_limiter.py           # Rate limiting utilities
│   ├── bt_signing.py             # Bittensor signature utilities
│   ├── crypto.py                 # Cryptographic utilities
│   └── settings.py               # Configuration management
├── 📊 tao20/                       # TAO20 specific modules
│   ├── __init__.py
│   └── validator.py              # Legacy validator implementation
├── 💼 emissions/                   # Emissions tracking
│   ├── __init__.py
│   └── snapshot.py               # Emissions snapshot management
├── 📄 contracts/                   # Smart contracts
│   ├── src/                      # Solidity contracts
│   │   ├── TAO20Index.sol        # Main index contract
│   │   ├── EnhancedTAO20Index.sol # Enhanced features
│   │   ├── Vault.sol             # Asset vault
│   │   ├── FeeManager.sol        # Fee management
│   │   └── ValidatorSet.sol      # Validator management
│   ├── foundry.toml              # Foundry configuration
│   └── script/                   # Deployment scripts
├── 🧪 tests/                       # Test suite
│   ├── test_tao20_integration.py # Integration tests
│   ├── test_incentive_mechanism.py # Incentive tests
│   └── creation/                 # Creation system tests
├── 📚 docs/                        # Documentation
│   ├── ARCHITECTURE.md          # System architecture
│   ├── CONTRACTS.md             # Smart contract docs
│   ├── VALIDATOR_SETUP.md       # Validator setup guide
│   └── MINER_SETUP.md           # Miner setup guide
├── 🌐 frontend/                    # Web interface
│   ├── tao20_minting_interface.js
│   └── concrete_mint_interface.js
├── 📋 templates/                   # Code templates
│   ├── miner_template.py
│   └── validator_template.py
├── 📊 subnet_data/                 # Data storage
├── 🔄 scripts/                     # Utility scripts
└── 📋 Configuration Files
    ├── requirements.txt           # Python dependencies
    ├── .env.example              # Environment template
    ├── Makefile                  # Build automation
    └── PROJECT_STRUCTURE.md     # This file
```

## 🎯 **Core Components**

### **🚀 Neurons (Entry Points)**
- **`neurons/miner.py`**: Professional CLI for TAO20 miners
- **`neurons/validator.py`**: Professional CLI for TAO20 validators
- **`neurons/miner/miner.py`**: Core miner implementation (Authorized Participant)
- **`neurons/validator/validator.py`**: Core validator implementation (Receipt Validator)

### **🏗️ Creation System**
- **`creation/epoch_manager.py`**: 14-day epoch management with creation files
- **`creation/basket_validator.py`**: All-or-nothing basket validation
- **`creation/request_manager.py`**: Creation request lifecycle management

### **💰 Incentive System**
- **`neurons/validator/incentive_manager.py`**: Sophisticated 5-tier reward system
- Volume-based competition with 10% minting bonus
- Bronze → Silver → Gold → Platinum → Diamond progression

### **🔧 Common Utilities**
- **`common/logging.py`**: WandB integration for professional monitoring
- **`common/precompiles.py`**: Bittensor precompile integration
- **`common/monitoring.py`**: System health monitoring

## 🔄 **Key Improvements from Reorganization**

### **✅ Professional Structure**
- **Standard Bittensor Layout**: Follows `neurons/` convention
- **Clean Naming**: Removed redundant `tao20_` prefixes
- **Logical Grouping**: Related functionality organized together

### **✅ Enhanced Monitoring**
- **WandB Integration**: Professional logging and metrics (inspired by Sturdy Subnet)
- **Graceful Shutdown**: Signal handling for clean termination
- **Comprehensive CLI**: Full argument parsing with help text

### **✅ Production Ready**
- **Error Handling**: Comprehensive exception management
- **Configuration**: Environment-based configuration
- **Documentation**: Clear structure and purpose

## 🚀 **Usage Examples**

### **Running a Miner**
```bash
python neurons/miner.py \
    --netuid 20 \
    --tao20.evm_addr 0x1234567890123456789012345678901234567890 \
    --tao20.api_url https://api.alphamind.ai \
    --min_creation_size 1000 \
    --log_level INFO
```

### **Running a Validator**
```bash
python neurons/validator.py \
    --netuid 20 \
    --tao20.api_url https://api.alphamind.ai \
    --min_attestation_interval 60 \
    --log_level INFO
```

### **Disabling WandB**
```bash
python neurons/miner.py --wandb.off [other args]
```

## 🎖️ **Quality Standards**

### **✅ Code Organization**
- **Single Responsibility**: Each file has a clear purpose
- **Dependency Injection**: Clean interfaces and abstractions
- **Type Hints**: Comprehensive type annotations

### **✅ Professional Practices**
- **Logging**: Structured logging with correlation IDs
- **Monitoring**: Real-time metrics and health checks
- **Testing**: Comprehensive test coverage

### **✅ Bittensor Alignment**
- **Standard Patterns**: Follows established Bittensor conventions
- **Precompile Integration**: Native blockchain interaction
- **Community Standards**: Professional presentation for ecosystem

This reorganized structure provides a clean, professional foundation that showcases the sophisticated TAO20 subnet architecture to the Bittensor community.
