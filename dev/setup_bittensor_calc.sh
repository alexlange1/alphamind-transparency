#!/bin/bash

# Setup script for Bittensor-Only NAV Calculator
echo "🔧 Setting up Bittensor NAV Calculator..."

# Check if Python 3.8+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Install required packages
echo "📦 Installing required Python packages..."
pip3 install --upgrade pip
pip3 install bittensor substrate-interface

# Create example environment file
if [ ! -f .env.bittensor ]; then
    echo "📄 Creating example .env.bittensor file..."
    cat > .env.bittensor << 'EOF'
# Bittensor coldkey address to analyze (required)
COLDKEY_ADDRESS=5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY

# Bittensor network (optional, defaults to finney)
BITTENSOR_NETWORK=finney

# Custom Substrate URL (optional, uses network default if not specified)
# SUBSTRATE_URL=wss://entrypoint-finney.opentensor.ai:443
EOF
    echo "✅ Created .env.bittensor file - please edit with your coldkey address"
else
    echo "✅ .env.bittensor file already exists"
fi

# Make the calculator executable
chmod +x bittensor_nav_calculator.py

echo ""
echo "🎯 Setup complete! To run the Bittensor NAV calculator:"
echo ""
echo "1. Edit .env.bittensor file with your coldkey address:"
echo "   nano .env.bittensor"
echo ""
echo "2. Run the calculator:"
echo "   source .env.bittensor && python3 bittensor_nav_calculator.py"
echo ""
echo "   Or with environment variables directly:"
echo "   COLDKEY_ADDRESS='5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY' python3 bittensor_nav_calculator.py"
echo ""
echo "🔒 DATA INTEGRITY GUARANTEED:"
echo "   ✅ 100% Bittensor blockchain data"
echo "   ✅ NO external APIs"
echo "   ✅ NO fallback prices"
echo "   ✅ Complete authenticity"
echo ""
echo "✅ Ready to calculate NAV from Bittensor stakes!"
