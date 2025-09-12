# 📚 TAO20 User Guide

This guide provides comprehensive instructions for setting up and running a **Miner (Authorized Participant)** or **Validator (NAV Attestor)** on the TAO20 subnet.

## 🚀 Quick Start

1.  **[Prerequisites](#-prerequisites)**: Ensure you have the required software and accounts.
2.  **[Installation](#-installation)**: Clone the repository and install dependencies.
3.  **[Configuration](#-configuration)**: Set up your environment variables and wallets.
4.  **[Running a Miner](#-running-a-miner)**: Start your miner neuron.
5.  **[Running a Validator](#-running-a-validator)**: Start your validator neuron.

---

## ✅ Prerequisites

### 1. Software
- **Python 3.8+**: [Download Python](https://www.python.org/downloads/)
- **Node.js & npm**: Required for smart contract development. [Download Node.js](https://nodejs.org/)
- **Foundry**: For smart contract testing and deployment. [Foundry Installation Guide](https://book.getfoundry.sh/getting-started/installation)
- **Git**: [Download Git](https://git-scm.com/downloads)

### 2. Bittensor
- **`btcli` Installed**: You must have the Bittensor CLI installed and configured. [Bittensor Setup Guide](https://docs.bittensor.com/getting-started/installation)
- **Bittensor Wallet**: A funded Bittensor wallet with a registered hotkey on the TAO20 subnet (Netuid 20).

### 3. BEVM (Blockchain)
- **BEVM RPC URL**: An RPC endpoint for the BEVM network (e.g., from Ankr, Infura, or your own node).
- **EVM Wallet**: An Ethereum/BEVM compatible wallet (like MetaMask) and its private key for your neuron.

---

## 💻 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/alphamind-project/alphamind.git
cd alphamind
```

### 2. Install Python Dependencies
Create a virtual environment and install the required Python packages.
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Install Smart Contract Dependencies
Navigate to the `contracts` directory and install the Node.js dependencies.
```bash
cd contracts
npm install
```

---

## ⚙️ Configuration

### 1. Environment Variables
The system is configured using environment variables. Copy the example file and edit it with your specific details.
```bash
cp env.example .env
```

**Edit the `.env` file:**

```env
# Bittensor Wallet Configuration
TAO20_WALLET_PATH="~/.bittensor/wallets/default"
TAO20_SOURCE_SS58="5..." # Your Bittensor hotkey SS58 address

# BEVM Configuration
TAO20_EVM_ADDR="0x..." # Your EVM address for receiving TAO20
BEVM_RPC_URL="https://your-bevm-rpc-url.com"

# TAO20 API
TAO20_API_URL="https://api.alphamind.ai" # Official API endpoint

# Neuron Configuration
BITTENSOR_NETWORK="finney" # or "mainnet"
TAO20_MINER_ID="your_unique_miner_id"
TAO20_VALIDATOR_ID="your_unique_validator_id"

# Logging & Monitoring (Optional)
WANDB_API_KEY="your_wandb_api_key"
```

### 2. Wallet Setup
Ensure your Bittensor wallet is properly configured and your hotkey is registered on the TAO20 subnet (Netuid 20).

```bash
# Verify your hotkey is registered
btcli s list
```

---

## 🤖 Running a Miner (Authorized Participant)

Miners are the liquidity providers of the TAO20 ecosystem. They are responsible for sourcing the 20 underlying subnet tokens and delivering them to the Vault to mint new TAO20.

### Starting the Miner
Use the `neurons/miner.py` script to start your miner. The script will automatically use the configuration from your `.env` file.

```bash
python neurons/miner.py \
    --wallet.name <your_wallet_name> \
    --wallet.hotkey <your_hotkey_name> \
    --netuid 20 \
    --logging.debug # Optional: for verbose logging
```

### Miner Operations
Once started, the miner will:
1.  Connect to the Bittensor network.
2.  Fetch the current portfolio weights from the `EpochManager`.
3.  Continuously monitor for arbitrage opportunities.
4.  When an opportunity is detected, it will:
    - Assemble the required asset basket.
    - Deliver the basket to the `Vault`.
    - Register the creation and poll for success.
5.  Log all activities and metrics.

---

## 🔍 Running a Validator (NAV Attestor)

Validators are the decentralized auditors of the TAO20 ecosystem. They are responsible for monitoring miner deliveries and providing accurate NAV attestations.

### Starting the Validator
Use the `neurons/validator.py` script to start your validator.

```bash
python neurons/validator.py \
    --wallet.name <your_wallet_name> \
    --wallet.hotkey <your_hotkey_name> \
    --netuid 20 \
    --logging.debug # Optional: for verbose logging
```

### Validator Operations
Once started, the validator will:
1.  Connect to the Bittensor network.
2.  Continuously monitor the `Vault` for new creation events.
3.  When a new creation is detected, it will:
    - Fetch the transaction details from the blockchain.
    - Calculate the exact NAV at the time of the receipt block.
    - Submit a signed attestation to the `Real-time NAV Service`.
4.  Track miner volumes and calculate rewards for the incentive mechanism.
5.  Log all activities and metrics.

---

## 🛠️ Advanced Configuration & Monitoring

### Custom Acquisition Strategy (Miners)
Miners can implement their own `AcquisitionStrategy` to source subnet tokens. See the `StakeStrategy` and `OTCStrategy` classes in `neurons/miner/miner.py` for examples.

### Monitoring
The neurons are integrated with Weights & Biases for real-time monitoring. If you provide a `WANDB_API_KEY` in your `.env` file, all metrics will be streamed to a personal dashboard.

### Health Checks
You can check the health of the system by querying the public API:
```bash
# Check API status
curl https://api.alphamind.ai/health

# Check current NAV
curl https://api.alphamind.ai/nav
```
