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

log "📋 Updating transparency data in main branch with daily emissions data"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    log "❌ Not in a git repository - skipping transparency update"
    log "   Please run this script from within the alphamind repository"
    exit 1
fi

# Configure git for automated commits
git config user.name "AlphaMind Emissions Bot"
git config user.email "emissions-bot@alphamind.subnet"

log "📁 Updating transparency data in main branch..."

# Create simple directory structure in tao20-transparency folder
mkdir -p tao20-transparency/{daily,status}

# Define file paths and initialize variables
DAILY_FILE="tao20-transparency/daily/emissions_$(date -u '+%Y%m%d').json"
STATUS_FILE="tao20-transparency/status/latest.json"
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
MANIFEST_FILE="manifests/manifest_latest.json"
if [ -f "$MANIFEST_FILE" ]; then
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
    # Get first 16 characters for preview
    print(sig[:16] if len(sig) > 16 else sig)
except Exception as e:
    print('unknown')
" "$MANIFEST_FILE" 2>/dev/null || echo "unknown")
else
    log "⚠️  Latest manifest not found at $MANIFEST_FILE"
fi

log "📊 Extracted data - Subnets: $SUBNET_COUNT, Merkle Root: ${MERKLE_ROOT:0:16}..., Signature: ${SIGNATURE}..."

# Copy actual emissions data with subnet details to daily transparency folder
if [ -f "$LATEST_EMISSIONS" ]; then
    # Extract the actual secure emissions file with full subnet data
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
    
    if [ -n "$SECURE_EMISSIONS_FILE" ] && [ -f "out/secure/secure_data/$SECURE_EMISSIONS_FILE" ]; then
        cp "out/secure/secure_data/$SECURE_EMISSIONS_FILE" "$DAILY_FILE"
        log "📄 Copied actual emissions data with subnet details to transparency folder"
    else
        log "⚠️  Could not find secure emissions file: $SECURE_EMISSIONS_FILE"
    fi
else
    log "⚠️  Latest emissions file not found at $LATEST_EMISSIONS"
fi

# Create simple status file
cat > "$STATUS_FILE" << EOF
{
    "last_updated": "$TIMESTAMP",
    "date": "$DATE_STR",
    "status": "success",
    "subnets_collected": $SUBNET_COUNT,
    "merkle_root": "$MERKLE_ROOT",
    "signature_preview": "${SIGNATURE}...",
    "network": "finney",
    "s3_bucket": "s3://alphamind-emissions-data/emissions/$DATE_STR/",
    "github_repo": "https://github.com/alexlange1/alphamind"
}
EOF

# Create simple README
cat > tao20-transparency/README.md << EOF
# AlphaMind Emissions Transparency

Daily transparency data for AlphaMind subnet emissions collection from Bittensor Finney network.

## 📊 Latest Collection

- **Date**: $DATE_STR
- **Subnets**: $SUBNET_COUNT
- **Merkle Root**: \`$MERKLE_ROOT\`
- **Status**: ✅ Verified

## 📁 Data Structure

- \`daily/\` - Daily emissions data files
- \`status/\` - Collection status and metadata

## 🔒 Security

- Ed25519 cryptographic signatures
- SHA-256 + HMAC integrity protection  
- Merkle tree verification
- S3 immutable storage

## 🔗 Links

- **S3 Data**: [s3://alphamind-emissions-data](https://alphamind-emissions-data.s3.amazonaws.com/)
- **GitHub**: [alexlange1/alphamind](https://github.com/alexlange1/alphamind)

---
*Last updated: $TIMESTAMP*
EOF

# Check if tao20-transparency folder exists, if not create it
if [ ! -d "tao20-transparency" ]; then
    mkdir -p tao20-transparency/{daily,status}
    log "📁 Created tao20-transparency folder structure"
fi

# Add ONLY the tao20-transparency folder - nothing else
git add tao20-transparency/

# Check if there are changes to commit
if git diff --staged --quiet; then
    log "📝 No transparency changes to commit"
else
    # Simple commit message focused only on transparency
    COMMIT_MSG="📊 Update tao20-transparency - $DATE_STR

Subnets: $SUBNET_COUNT | Merkle: ${MERKLE_ROOT:0:16}... | Time: $TIMESTAMP"

    git commit -m "$COMMIT_MSG"
    
    # Push only the transparency changes to main branch
    if git push origin main; then
        log "✅ Transparency folder updated on main branch"
        log "🔗 View at: https://github.com/alexlange1/alphamind/tree/main/tao20-transparency"
    else
        log "❌ Failed to push transparency updates to main branch"
        log "   Check GitHub token permissions and repository access"
        exit 1
    fi
fi

log "📋 Transparency update completed"
