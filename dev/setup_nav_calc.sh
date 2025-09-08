#!/bin/bash

# Setup script for Real NAV Calculator
echo "🔧 Setting up Real NAV Calculator..."

# Check if Python 3.8+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Install required packages
echo "📦 Installing required Python packages..."
pip3 install --upgrade pip
pip3 install web3 aiohttp bittensor

# Create example environment file
if [ ! -f .env ]; then
    echo "📄 Creating example .env file..."
    cat > .env << 'EOF'
# Web3 RPC URL (required)
# Get from Infura, Alchemy, or other provider
WEB3_RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID

# Wallet address to analyze (required)
WALLET_ADDRESS=0x742d35Cc6634C0532925a3b8D1d9C3EEaf5C4472

# Bittensor network (optional, defaults to finney)
BITTENSOR_NETWORK=finney
EOF
    echo "✅ Created .env file - please edit with your values"
else
    echo "✅ .env file already exists"
fi

# Make the calculator executable
chmod +x real_nav_calculator.py

echo ""
echo "🎯 Setup complete! To run the NAV calculator:"
echo ""
echo "1. Edit .env file with your RPC URL and wallet address:"
echo "   nano .env"
echo ""
echo "2. Run the calculator:"
echo "   python3 real_nav_calculator.py"
echo ""
echo "   Or with environment variables directly:"
echo "   WEB3_RPC_URL='your-rpc-url' WALLET_ADDRESS='wallet-address' python3 real_nav_calculator.py"
echo ""
echo "✅ Ready to calculate real NAV from any wallet!"
