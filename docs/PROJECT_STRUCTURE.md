# Project Structure

This document provides a detailed overview of the Alphamind project structure and organization.

## 📁 Root Directory

```
alphamind/
├── 📄 README.md              # Project overview and quick start
├── 📄 CONTRIBUTING.md        # Contribution guidelines
├── 📄 CHANGELOG.md           # Version history and changes
├── 📄 LICENSE                # MIT License
├── 📄 Makefile               # Development commands
├── 📄 requirements.txt       # Python dependencies
├── 📄 env.example            # Environment variables template
├── 📄 .gitignore             # Git ignore rules
├── 📄 .gitmodules            # Git submodules
├── 📁 .github/               # GitHub workflows and templates
├── 📁 .venv/                 # Python virtual environment
├── 📁 contracts/             # Smart contracts (Solidity)
├── 📁 subnet/                # Bittensor subnet implementation
├── 📁 frontend/              # Web interface
├── 📁 docs/                  # Documentation
├── 📁 tests/                 # Integration tests
├── 📁 scripts/               # Deployment and utility scripts
├── 📁 logs/                  # Log files and test outputs
├── 📁 subnet_data/           # Subnet data and reports
└── 📁 templates/             # Code templates
```

## 🏗️ Core Components

### Smart Contracts (`contracts/`)

```
contracts/
├── 📁 src/                   # Contract source files
│   ├── 📄 TAO20.sol         # Main index token contract
│   ├── 📄 Router.sol        # Minting/redemption router
│   ├── 📄 FeeManager.sol    # Fee collection and distribution
│   ├── 📄 ValidatorSet.sol  # Validator management
│   ├── 📄 Timelock.sol      # Governance timelock
│   └── 📄 interfaces/       # Contract interfaces
├── 📁 test/                  # Contract tests
├── 📁 script/                # Deployment scripts
├── 📁 lib/                   # Dependencies (Forge)
├── 📁 out/                   # Build artifacts
├── 📄 foundry.toml          # Foundry configuration
└── 📄 .env                  # Contract environment variables
```

### Bittensor Subnet (`subnet/`)

```
subnet/
├── 📁 miner/                 # Miner implementation
│   ├── 📄 tao20_miner.py    # Main miner logic
│   └── 📄 __init__.py       # Package initialization
├── 📁 validator/             # Validator implementation
│   ├── 📄 tao20_validator.py # Main validator logic
│   └── 📄 __init__.py       # Package initialization
├── 📁 api/                   # REST API
│   ├── 📄 main.py           # FastAPI application
│   ├── 📄 routes/           # API route handlers
│   └── 📄 models/           # Pydantic models
├── 📁 common/                # Shared utilities
│   ├── 📄 config.py         # Configuration management
│   ├── 📄 database.py       # Database utilities
│   ├── 📄 logging.py        # Logging configuration
│   └── 📄 utils.py          # Common utilities
├── 📁 tao20/                 # TAO20-specific logic
│   ├── 📄 index.py          # Index management
│   ├── 📄 nav.py            # NAV calculation
│   └── 📄 rebalancing.py    # Rebalancing logic
├── 📁 vault/                 # Vault management
├── 📁 keeper/                # Keeper bot logic
├── 📁 emissions/             # Emissions tracking
├── 📁 sim/                   # Simulation tools
├── 📁 specs/                 # Subnet specifications
├── 📄 requirements.txt       # Python dependencies
├── 📄 cli.py                # Command-line interface
├── 📄 dev_run.sh            # Development runner
└── 📄 Makefile              # Subnet-specific commands
```

### Frontend (`frontend/`)

```
frontend/
├── 📁 src/                   # Source code
│   ├── 📁 components/        # React components
│   ├── 📁 pages/            # Page components
│   ├── 📁 hooks/            # Custom React hooks
│   ├── 📁 utils/            # Utility functions
│   ├── 📁 styles/           # CSS/styling
│   └── 📄 App.tsx           # Main application
├── 📁 public/                # Static assets
├── 📄 package.json           # Node.js dependencies
├── 📄 tsconfig.json         # TypeScript configuration
├── 📄 vite.config.ts        # Vite configuration
└── 📄 README.md             # Frontend documentation
```

### Documentation (`docs/`)

```
docs/
├── 📄 ARCHITECTURE.md        # System architecture
├── 📄 API.md                # API reference
├── 📄 CONTRACTS.md          # Smart contract documentation
├── 📄 MINER_SETUP.md        # Miner setup guide
├── 📄 VALIDATOR_SETUP.md    # Validator setup guide
├── 📄 PROJECT_STRUCTURE.md  # This file
├── 📁 images/               # Documentation images
└── 📄 mkdocs.yml           # Documentation site configuration
```

### Scripts (`scripts/`)

```
scripts/
├── 📁 deployment/            # Deployment scripts
│   ├── 📄 deploy.sh         # Main deployment script
│   ├── 📄 cloudformation.json # AWS CloudFormation template
│   └── 📄 docker-compose.yml # Docker deployment
├── 📁 utils/                 # Utility scripts
│   ├── 📄 update_emissions.sh # Emissions update script
│   ├── 📄 update_nav_10m.sh  # NAV update script
│   ├── 📄 local-test.sh      # Local testing script
│   ├── 📄 verify_portfolio_weights.py # Portfolio verification
│   └── 📄 alphamind          # Main utility script
└── 📄 README.md             # Scripts documentation
```

### Tests (`tests/`)

```
tests/
├── 📄 test_tao20.py         # TAO20 integration tests
├── 📄 test_security.py      # Security tests
├── 📄 test_consensus.py     # Consensus mechanism tests
├── 📄 test_eligibility.py   # Eligibility tests
├── 📄 test_reports.py       # Report generation tests
├── 📄 test_aggregate_slippage.py # Slippage tests
├── 📄 test_enhanced_tao20_system.py # System integration tests
├── 📄 test_medians.py       # Median calculation tests
├── 📄 test_property_conservation.py # Property tests
├── 📄 test_publish_onchain.py # On-chain publishing tests
├── 📄 test_readyz.py        # Health check tests
├── 📄 test_reports_signatures.py # Signature tests
├── 📄 test_residuals.py     # Residual calculation tests
├── 📄 test_slashing_log.py  # Slashing mechanism tests
├── 📄 test_weightset_epoch.py # Weight set tests
├── 📄 test_stress.py        # Stress tests
└── 📄 conftest.py           # Test configuration
```

### Logs (`logs/`)

```
logs/
├── 📄 nav_update.log        # NAV update logs
├── 📄 nav_update.err        # NAV update errors
├── 📁 NAV_test/             # NAV test outputs
└── 📄 README.md             # Logs documentation
```

## 🔧 Development Workflow

### File Naming Conventions

- **Python files**: `snake_case.py`
- **JavaScript/TypeScript files**: `camelCase.ts` or `PascalCase.tsx`
- **Solidity files**: `PascalCase.sol`
- **Configuration files**: `kebab-case.ext`
- **Documentation files**: `UPPER_CASE.md`

### Import Organization

#### Python
```python
# Standard library imports
import os
import sys
from typing import Dict, List

# Third-party imports
import bittensor as bt
import web3

# Local imports
from subnet.common.config import Config
from subnet.tao20.index import IndexManager
```

#### JavaScript/TypeScript
```typescript
// Third-party imports
import React from 'react';
import { useState, useEffect } from 'react';

// Local imports
import { useWallet } from '../hooks/useWallet';
import { formatAmount } from '../utils/formatters';
```

### Code Organization Principles

1. **Separation of Concerns**: Each module has a single responsibility
2. **Dependency Inversion**: High-level modules don't depend on low-level modules
3. **Interface Segregation**: Clients depend only on interfaces they use
4. **Single Responsibility**: Each class/function has one reason to change
5. **Open/Closed**: Open for extension, closed for modification

## 📊 Data Flow

```
User Request → Frontend → API → Validator Network → Smart Contract
                ↓
            Database ← Logs ← Monitoring
```

## 🔒 Security Considerations

- **Private keys**: Never committed to repository
- **Environment variables**: Used for sensitive configuration
- **Input validation**: All inputs validated at boundaries
- **Access control**: Proper authorization checks
- **Audit trails**: All actions logged for security

## 🚀 Deployment Structure

### Production Environment

```
Production/
├── 📁 miners/               # Miner instances
├── 📁 validators/           # Validator instances
├── 📁 api/                  # API servers
├── 📁 frontend/             # Web servers
├── 📁 monitoring/           # Monitoring stack
└── 📁 backup/               # Backup storage
```

### Development Environment

```
Development/
├── 📁 local/                # Local development
├── 📁 staging/              # Staging environment
└── 📁 testing/              # Test environment
```

## 📈 Monitoring and Observability

- **Logs**: Structured logging with correlation IDs
- **Metrics**: Prometheus metrics for performance monitoring
- **Tracing**: Distributed tracing for request flows
- **Alerts**: Automated alerting for critical issues
- **Dashboards**: Grafana dashboards for visualization

## 🔄 CI/CD Pipeline

```
Code → Tests → Build → Deploy → Monitor
  ↓      ↓      ↓       ↓        ↓
GitHub → Jest → Docker → AWS → Grafana
```

This structure ensures maintainability, scalability, and developer productivity while following industry best practices.
