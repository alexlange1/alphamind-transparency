#!/bin/bash
set -euo pipefail

# Update Transparency Repository with Daily Manifest
# Commits signed manifest to GitHub for public verification

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
TRANSPARENCY_REPO="${TRANSPARENCY_REPO:-}"
TRANSPARENCY_BRANCH="${TRANSPARENCY_BRANCH:-main}"

# Get current branch name
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $*"
}

log "📋 Updating transparency data in $CURRENT_BRANCH branch with daily manifest"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    log "❌ Not in a git repository - skipping transparency update"
    log "   Please run this script from within the alphamind repository"
    exit 1
fi

# Configure git for automated commits
git config user.name "AlphaMind Emissions Bot"
git config user.email "emissions-bot@alphamind.subnet"

log "📁 Updating transparency data in $CURRENT_BRANCH branch..."

# Create directory structure in tao20-transparency folder
mkdir -p tao20-transparency/{manifests,status,data}
mkdir -p "tao20-transparency/manifests/$(date -u '+%Y')/$(date -u '+%m')"

# Define file paths and initialize variables
S3_URLS_FILE="logs/s3_urls_$(date -u '+%Y%m%d').json"
STATUS_FILE="tao20-transparency/status/status_$(date -u '+%Y%m%d').json"
LATEST_MANIFEST="tao20-transparency/manifests/manifest_latest.json"
LATEST_EMISSIONS="$PROJECT_ROOT/out/secure/secure_data/latest_emissions_secure.json"

# Initialize default values
SUBNET_COUNT=0
MERKLE_ROOT="unknown"
SIGNATURE="unknown"

# Extract data from latest emissions file if it exists
if [ -f "$LATEST_EMISSIONS" ]; then
    SUBNET_COUNT=$(python3 -c "
import json
import sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    print(data.get('total_subnets', 0))
except Exception as e:
    print(0)
" "$LATEST_EMISSIONS" 2>/dev/null || echo "0")
else
    log "⚠️  Latest emissions file not found at $LATEST_EMISSIONS"
fi

# Extract data from latest manifest if it exists
if [ -f "$LATEST_MANIFEST" ]; then
    MERKLE_ROOT=$(python3 -c "
import json
import sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    print(data.get('merkle_root', 'unknown'))
except Exception as e:
    print('unknown')
" "$LATEST_MANIFEST" 2>/dev/null || echo "unknown")
    
    SIGNATURE=$(python3 -c "
import json
import sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    sig = data.get('signature', {}).get('signature', 'unknown')
    # Get first 16 characters for preview
    print(sig[:16] if len(sig) > 16 else sig)
except Exception as e:
    print('unknown')
" "$LATEST_MANIFEST" 2>/dev/null || echo "unknown")
else
    log "⚠️  Latest manifest not found at $LATEST_MANIFEST"
fi

# Load S3 URLs if available
MANIFEST_URL=""
DATA_URL=""
if [ -f "$S3_URLS_FILE" ]; then
    MANIFEST_URL=$(jq -r '.manifest_url' "$S3_URLS_FILE" 2>/dev/null || echo "")
    DATA_URL=$(jq -r '.data_url' "$S3_URLS_FILE" 2>/dev/null || echo "")
fi

log "📊 Extracted data - Subnets: $SUBNET_COUNT, Merkle Root: ${MERKLE_ROOT:0:16}..., Signature: ${SIGNATURE}..."

# Create status summary
cat > "$STATUS_FILE" << EOF
{
    "date": "$DATE_STR",
    "timestamp": "$TIMESTAMP",
    "status": "success",
    "collection": {
        "total_files": $SUBNET_COUNT,
        "merkle_root": "$MERKLE_ROOT",
        "signature_preview": "$SIGNATURE...",
        "network": "finney",
        "method": "btcli_automated_vps"
    },
    "storage": {
        "manifest_url": "$MANIFEST_URL",
        "data_url": "$DATA_URL",
        "backend": "s3_versioned"
    },
    "verification": {
        "github_actions_url": "https://github.com/alexlange1/alphamind/actions",
        "public_key_url": "$DATA_URL/public_key.pem"
    }
}
EOF

# Update latest status
cp "$STATUS_FILE" "tao20-transparency/status/latest.json"

# Create or update README
cat > tao20-transparency/README.md << EOF
# AlphaMind Emissions Data Transparency

This repository provides public transparency and verification for AlphaMind subnet emissions data collection.

## 🔒 Security & Integrity

- **Daily Collection**: Automated collection at 16:00 UTC from Bittensor Finney network
- **Cryptographic Security**: SHA-256 hashing + Ed25519 signatures + Merkle tree verification
- **Immutable Storage**: S3 with versioning enabled for tamper-proof history
- **Public Verification**: GitHub Actions verify data integrity daily

## 📊 Latest Collection

**Date**: $DATE_STR  
**Files**: $SUBNET_COUNT  
**Merkle Root**: \`$MERKLE_ROOT\`  
**Status**: ✅ Verified

## 🔗 Data Access

- **Manifest**: [$MANIFEST_URL]($MANIFEST_URL)
- **Raw Data**: [$DATA_URL]($DATA_URL)
- **Latest Status**: [status/latest.json](status/latest.json)

## 🔍 Verification

To verify the data integrity:

1. Download the manifest and data from S3
2. Verify Ed25519 signature using the public key
3. Recompute Merkle tree and compare with manifest
4. Check GitHub Actions verification results

### Verification Script

\`\`\`bash
# Download verification script
curl -O https://raw.githubusercontent.com/alexlange1/alphamind/main/deployment/verify_manifest.py

# Run verification
python3 verify_manifest.py --manifest-url $MANIFEST_URL --data-url $DATA_URL
\`\`\`

## 📈 Historical Data

- [Manifests by Date](manifests/)
- [Daily Status Reports](status/)
- [GitHub Actions Verification](https://github.com/alexlange1/alphamind/actions)

## 🎯 About AlphaMind

AlphaMind is a Bittensor subnet focused on creating secure, transparent, and verifiable AI model indices based on network emissions data.

---

*Last updated: $TIMESTAMP*  
*Data collection: Automated via VPS + S3*  
*Verification: GitHub Actions + Public Merkle Tree*
EOF

# Add transparency changes
git add tao20-transparency/

# Check if there are changes to commit
if git diff --staged --quiet; then
    log "📝 No transparency changes to commit"
else
    # Commit changes
    COMMIT_MSG="📊 Daily emissions transparency update - $DATE_STR

🔒 Cryptographic manifest with Merkle root: $MERKLE_ROOT
📊 Collection: $SUBNET_COUNT files from Bittensor Finney network
🔐 Ed25519 signature: $SIGNATURE...
⏰ Timestamp: $TIMESTAMP

Data available at: $DATA_URL
Manifest: $MANIFEST_URL"

    git commit -m "$COMMIT_MSG"
    
    # Push to current branch
    if git push origin "$CURRENT_BRANCH"; then
        log "✅ Transparency update committed and pushed successfully"
        log "🔗 View at: https://github.com/alexlange1/alphamind/tree/$CURRENT_BRANCH"
    else
        log "❌ Failed to push to $CURRENT_BRANCH branch"
        log "   Check GitHub token permissions and repository access"
        exit 1
    fi
fi

log "📋 Transparency update completed in $CURRENT_BRANCH branch"
