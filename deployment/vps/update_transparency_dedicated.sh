#!/bin/bash
set -euo pipefail

# Update Dedicated Transparency Repository with Daily Emissions
# Pushes emissions data to separate public transparency repository

# Determine project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

# Load environment variables
if [ -f secrets/.env ]; then
    source secrets/.env
fi

# Configuration
DATE_STR=$(date -u '+%Y-%m-%d')
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
TRANSPARENCY_REPO_URL="${TRANSPARENCY_REPO_URL:-https://${GITHUB_TOKEN}@github.com/alexlange1/alphamind-transparency.git}"
TEMP_DIR="/tmp/alphamind_transparency_$$"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $*"
}

log "📋 Updating dedicated transparency repository with emissions data"

# Verify GitHub token is available
if [ -z "${GITHUB_TOKEN:-}" ]; then
    log "❌ GITHUB_TOKEN not set - cannot publish to transparency repository"
    exit 1
fi

# Clean up any existing temp directory
rm -rf "$TEMP_DIR"

# Clone the dedicated transparency repository
log "📥 Cloning transparency repository..."
if ! git clone "$TRANSPARENCY_REPO_URL" "$TEMP_DIR"; then
    log "❌ Failed to clone transparency repository"
    log "   Check token permissions and repository URL"
    exit 1
fi

cd "$TEMP_DIR"

# Configure git for automated commits
git config user.name "AlphaMind Emissions Bot"
git config user.email "emissions-bot@alphamind.subnet"

# Create directory structure
mkdir -p {daily,manifests,status,tao20}

# Define file paths and initialize variables
DAILY_FILE="daily/emissions_$(date -u '+%Y%m%d').json"
STATUS_FILE="status/latest.json"
MANIFEST_FILE="manifests/manifest_$(date -u '+%Y%m%d').json"
LATEST_EMISSIONS="$PROJECT_ROOT/out/secure/secure_data/latest_emissions_secure.json"

# Initialize default values
SUBNET_COUNT=0
TOTAL_TAO=0
MERKLE_ROOT="unknown"
SIGNATURE="unknown"

# Extract data from latest emissions file if it exists
if [ -f "$LATEST_EMISSIONS" ]; then
    log "📊 Processing emissions data..."
    
    # Get the actual secure emissions file path
    SECURE_EMISSIONS_FILE=$(python3 -c "
import json
import sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    print(data.get('latest_file', ''))
except Exception as e:
    print('')
" "$LATEST_EMISSIONS" 2>/dev/null)
    
    if [ -n "$SECURE_EMISSIONS_FILE" ] && [ -f "$PROJECT_ROOT/out/secure/secure_data/$SECURE_EMISSIONS_FILE" ]; then
        # Copy the actual emissions data with subnet details (secure file has percentages)
        cp "$PROJECT_ROOT/out/secure/secure_data/$SECURE_EMISSIONS_FILE" "$DAILY_FILE"
        
        # Also copy the legacy file with absolute TAO amounts for reference
        LEGACY_FILE="daily/emissions_legacy_$(date -u '+%Y%m%d').json"
        if [ -f "$PROJECT_ROOT/out/emissions_daily_$(date -u '+%Y%m%d').json" ]; then
            cp "$PROJECT_ROOT/out/emissions_daily_$(date -u '+%Y%m%d').json" "$LEGACY_FILE"
        fi
        
        # Extract statistics from secure file (percentages) and legacy file (TAO amounts)
        SUBNET_COUNT=$(python3 -c "
import json
import sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    emissions_pct = data.get('emissions_percentage_by_netuid', {})
    print(len(emissions_pct))
except Exception as e:
    print(0)
" "$DAILY_FILE" 2>/dev/null || echo "0")

        # Get total TAO from legacy file if available
        LEGACY_PATH="$PROJECT_ROOT/out/emissions_daily_$(date -u '+%Y%m%d').json"
        TOTAL_TAO=$(python3 -c "
import json
import sys
import os
try:
    if os.path.exists(sys.argv[1]):
        with open(sys.argv[1]) as f:
            data = json.load(f)
        emissions = data.get('emissions_by_netuid', {})
        total = sum(float(v) for v in emissions.values())
        print(f'{total:.6f}')
    else:
        print('0.000000')
except Exception as e:
    print('0.000000')
" "$LEGACY_PATH" 2>/dev/null || echo "0.000000")
        
        log "📄 Copied emissions data: $SUBNET_COUNT subnets, $TOTAL_TAO TAO total"
    else
        log "⚠️  Could not find secure emissions file: $SECURE_EMISSIONS_FILE"
    fi
else
    log "⚠️  Latest emissions file not found at $LATEST_EMISSIONS"
fi

# Copy manifest if available
MANIFEST_SOURCE="$PROJECT_ROOT/manifests/manifest_latest.json"
if [ -f "$MANIFEST_SOURCE" ]; then
    cp "$MANIFEST_SOURCE" "$MANIFEST_FILE"
    
    MERKLE_ROOT=$(python3 -c "
import json
import sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    print(data.get('merkle_root', 'unknown'))
except Exception as e:
    print('unknown')
" "$MANIFEST_FILE" 2>/dev/null || echo "unknown")
    
    SIGNATURE=$(python3 -c "
import json
import sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    sig = data.get('signature', {}).get('signature', 'unknown')
    print(sig[:16] if len(sig) > 16 else sig)
except Exception as e:
    print('unknown')
" "$MANIFEST_FILE" 2>/dev/null || echo "unknown")
    
    log "🔐 Copied manifest: Merkle root ${MERKLE_ROOT:0:16}..."
fi

# Copy TAO20 index data if available
TAO20_LATEST="$PROJECT_ROOT/out/tao20_index_latest.json"
TAO20_PUBLICATION_RECORD="$PROJECT_ROOT/out/last_tao20_publication.json"

if [ -f "$TAO20_LATEST" ]; then
    TAO20_FILE="tao20/tao20_index_latest.json"
    cp "$TAO20_LATEST" "$TAO20_FILE"
    
    # Also copy timestamped version if it exists
    TAO20_TIMESTAMPED=$(ls "$PROJECT_ROOT/out/tao20_index_$(date -u '+%Y%m%d')_"*.json 2>/dev/null | tail -1 || echo "")
    if [ -n "$TAO20_TIMESTAMPED" ] && [ -f "$TAO20_TIMESTAMPED" ]; then
        TAO20_DAILY_FILE="tao20/tao20_index_$(date -u '+%Y%m%d').json"
        cp "$TAO20_TIMESTAMPED" "$TAO20_DAILY_FILE"
    fi
    
    log "📊 Copied TAO20 index data"
else
    log "ℹ️  No TAO20 index data available"
fi

# Copy TAO20 publication record if available
if [ -f "$TAO20_PUBLICATION_RECORD" ]; then
    TAO20_STATUS_FILE="tao20/publication_status.json"
    cp "$TAO20_PUBLICATION_RECORD" "$TAO20_STATUS_FILE"
    log "📋 Copied TAO20 publication status"
fi

# Copy any TAO20 Sunday publication directories if they exist
TAO20_SUNDAY_DIR="$PROJECT_ROOT/out/tao20_sunday_$(date -u '+%Y%m%d')"
if [ -d "$TAO20_SUNDAY_DIR" ]; then
    TAO20_PUB_DIR="tao20/sunday_$(date -u '+%Y%m%d')"
    cp -r "$TAO20_SUNDAY_DIR" "$TAO20_PUB_DIR"
    log "📦 Copied TAO20 Sunday publication package"
fi

# Extract TAO20 info if available
TAO20_CONSTITUENTS=0
TAO20_LAST_UPDATE="N/A"
TAO20_NEXT_PUBLICATION="N/A"

if [ -f "$TAO20_LATEST" ]; then
    TAO20_CONSTITUENTS=$(python3 -c "
import json
import sys
try:
    with open('$TAO20_FILE') as f:
        data = json.load(f)
    constituents = data.get('tao20_constituents', [])
    print(len(constituents))
except Exception as e:
    print(0)
" 2>/dev/null || echo "0")
fi

if [ -f "$TAO20_PUBLICATION_RECORD" ]; then
    TAO20_LAST_UPDATE=$(python3 -c "
import json
import sys
try:
    with open('$TAO20_STATUS_FILE') as f:
        data = json.load(f)
    print(data.get('timestamp', 'N/A'))
except Exception as e:
    print('N/A')
" 2>/dev/null || echo "N/A")
    
    TAO20_NEXT_PUBLICATION=$(python3 -c "
import json
import sys
try:
    with open('$TAO20_STATUS_FILE') as f:
        data = json.load(f)
    print(data.get('next_publication_due', 'N/A'))
except Exception as e:
    print('N/A')
" 2>/dev/null || echo "N/A")
fi

# Create status file
cat > "$STATUS_FILE" << EOF
{
    "last_updated": "$TIMESTAMP",
    "date": "$DATE_STR",
    "status": "success",
    "emissions": {
        "subnets_collected": $SUBNET_COUNT,
        "total_tao_emissions": $TOTAL_TAO,
        "merkle_root": "$MERKLE_ROOT",
        "signature_preview": "${SIGNATURE}...",
        "network": "finney",
        "collection_method": "btcli_automated_secure"
    },
    "tao20": {
        "constituents_count": $TAO20_CONSTITUENTS,
        "last_update": "$TAO20_LAST_UPDATE",
        "next_publication": "$TAO20_NEXT_PUBLICATION",
        "index_available": $([ -f "$TAO20_LATEST" ] && echo "true" || echo "false")
    },
    "storage": {
        "s3_bucket": "s3://alphamind-emissions-data/emissions/$(date -u '+%Y/%m/%d')/"
    },
    "repository": {
        "github_repo": "https://github.com/alexlange1/alphamind-transparency",
        "transparency_data": "https://github.com/alexlange1/alphamind-transparency/tree/main"
    }
}
EOF

# Create/update README
cat > README.md << EOF
# 🌟 AlphaMind Emissions Transparency

**Real-time transparency for TAO20 subnet emissions from Bittensor Finney network**

## 📊 Latest Collection - $DATE_STR

- **Subnets Tracked**: $SUBNET_COUNT
- **Total TAO Emissions**: $TOTAL_TAO TAO
- **Collection Time**: $TIMESTAMP
- **Status**: ✅ Verified & Cryptographically Signed

## 🎯 TAO20 Index Status - $DATE_STR

- **Index Constituents**: $TAO20_CONSTITUENTS subnets
- **Last Publication**: $TAO20_LAST_UPDATE
- **Next Publication**: $TAO20_NEXT_PUBLICATION
- **Index Available**: $([ -f "tao20/tao20_index_latest.json" ] && echo "✅ Yes" || echo "⏳ Pending")

## 📁 Repository Structure

### \`daily/\` - Daily Emissions Data
- Raw subnet emissions data from Bittensor network
- JSON format with full subnet breakdown
- Cryptographically signed and verified

### \`tao20/\` - TAO20 Index Composition
- Latest TAO20 index with top 20 subnet constituents
- Biweekly Sunday publication packages
- Index weights and performance metrics
- Publication status and scheduling

### \`manifests/\` - Cryptographic Verification
- SHA-256 + HMAC integrity protection
- Ed25519 digital signatures  
- Merkle tree verification data

### \`status/\` - Collection Metadata
- Collection timestamps and statistics
- Network status and verification info
- S3 storage links and GitHub references
- TAO20 publication status and next update schedule

## 🔒 Security & Verification

- **Cryptographic Signatures**: Every data file is Ed25519 signed
- **Integrity Protection**: SHA-256 + HMAC prevents tampering
- **Merkle Tree Verification**: Mathematical proof of data consistency
- **Immutable Storage**: S3 versioning ensures historical data preservation
- **Public Transparency**: All data publicly verifiable on GitHub

## 🔗 Data Sources & Links

- **Primary Data**: [S3 Bucket](https://alphamind-emissions-data.s3.amazonaws.com/)
- **Main Repository**: [alexlange1/alphamind](https://github.com/alexlange1/alphamind)
- **Bittensor Network**: Finney (Production)
- **Collection Method**: \`btcli\` automated secure collection

## 📈 Top Performing Subnets (Last Collection)

$(python3 -c "
import json
import sys
import os
try:
    # Read percentage data from secure file
    if os.path.exists('$DAILY_FILE'):
        with open('$DAILY_FILE') as f:
            secure_data = json.load(f)
        emissions_pct = secure_data.get('emissions_percentage_by_netuid', {})
        
        # Read TAO amounts from legacy file if available
        legacy_file = 'daily/emissions_legacy_$(date -u '+%Y%m%d').json'
        emissions_tao = {}
        if os.path.exists(legacy_file):
            with open(legacy_file) as f:
                legacy_data = json.load(f)
            emissions_tao = legacy_data.get('emissions_by_netuid', {})
        
        if emissions_pct:
            sorted_emissions = sorted(emissions_pct.items(), key=lambda x: float(x[1]), reverse=True)[:10]
            for i, (netuid, pct) in enumerate(sorted_emissions, 1):
                pct_val = float(pct) * 100
                tao_amount = float(emissions_tao.get(netuid, 0)) if emissions_tao else 0
                if tao_amount > 0:
                    print(f'{i}. **Subnet {netuid}**: {pct_val:.2f}% ({tao_amount:.2f} TAO)')
                else:
                    print(f'{i}. **Subnet {netuid}**: {pct_val:.2f}%')
        else:
            print('Data processing in progress...')
    else:
        print('Collection in progress...')
except Exception as e:
    print('Data processing in progress...')
" 2>/dev/null || echo "Data processing in progress...")

---

*Last updated: $TIMESTAMP*  
*Automated by AlphaMind Emissions Bot*
EOF

log "📝 Generated transparency files"

# Add all files to git
git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    log "📝 No changes to commit"
else
    # Commit with detailed message
    COMMIT_MSG="📊 Daily emissions update - $DATE_STR

🔢 Subnets: $SUBNET_COUNT
💰 Total TAO: $TOTAL_TAO
🔐 Merkle: ${MERKLE_ROOT:0:16}...
⏰ Time: $TIMESTAMP

Automated collection from Bittensor Finney network via btcli"

    git commit -m "$COMMIT_MSG"
    
    # Push to main branch
    if git push origin main; then
        log "✅ Transparency data published successfully"
        log "🔗 View at: https://github.com/alexlange1/alphamind-transparency"
    else
        log "❌ Failed to push transparency data"
        exit 1
    fi
fi

# Clean up
cd "$PROJECT_ROOT"
rm -rf "$TEMP_DIR"

log "📋 Transparency publication completed"
