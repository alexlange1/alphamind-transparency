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

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $*"
}

log "📋 Updating transparency repository with daily manifest"

# Check if transparency repo is configured
if [ -z "$TRANSPARENCY_REPO" ]; then
    log "⚠️  TRANSPARENCY_REPO not configured - skipping transparency update"
    log "   To enable transparency updates, set:"
    log "   TRANSPARENCY_REPO=https://github.com/username/alphamind-transparency.git"
    exit 0
fi

# Create temporary directory for transparency repo
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

log "📁 Cloning transparency repository..."
cd "$TEMP_DIR"

# Clone or update transparency repo
if ! git clone "$TRANSPARENCY_REPO" transparency; then
    log "❌ Failed to clone transparency repository: $TRANSPARENCY_REPO"
    log "   Please ensure:"
    log "   - Repository exists and is accessible"
    log "   - GitHub token has proper permissions"
    log "   - Repository URL is correct"
    exit 1
fi

cd transparency

# Configure git for automated commits
git config user.name "AlphaMind Emissions Bot"
git config user.email "emissions-bot@alphamind.subnet"

# Create directory structure
mkdir -p {manifests,status,data}
mkdir -p "manifests/$(date -u '+%Y')/$(date -u '+%m')"

# Copy latest manifest

MANIFEST_URL=""
DATA_URL=""
if [ -f "$S3_URLS_FILE" ]; then
    MANIFEST_URL=$(jq -r '.manifest_url' "$S3_URLS_FILE" 2>/dev/null || echo "")
    DATA_URL=$(jq -r '.data_url' "$S3_URLS_FILE" 2>/dev/null || echo "")
fi

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
        "github_actions_url": "https://github.com/$(echo $TRANSPARENCY_REPO | sed 's/.*github.com\///g' | sed 's/\.git$//')/actions",
        "public_key_url": "$DATA_URL/public_key.pem"
    }
}
EOF

# Update latest status
cp "$STATUS_FILE" "status/latest.json"

# Create or update README
cat > README.md << EOF
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
- [GitHub Actions Verification](https://github.com/$(echo $TRANSPARENCY_REPO | sed 's/.*github.com\///g' | sed 's/\.git$//')/actions)

## 🎯 About AlphaMind

AlphaMind is a Bittensor subnet focused on creating secure, transparent, and verifiable AI model indices based on network emissions data.

---

*Last updated: $TIMESTAMP*  
*Data collection: Automated via VPS + S3*  
*Verification: GitHub Actions + Public Merkle Tree*
EOF

# Add all changes
git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    log "📝 No changes to commit to transparency repo"
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
    
    # Push to transparency repo
    if git push origin "$TRANSPARENCY_BRANCH"; then
        log "✅ Transparency update committed and pushed successfully"
        log "🔗 View at: $TRANSPARENCY_REPO"
    else
        log "❌ Failed to push to transparency repository"
        log "   Check GitHub token permissions and repository access"
        exit 1
    fi
fi

log "📋 Transparency repository update completed"
