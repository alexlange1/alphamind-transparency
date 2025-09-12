#!/bin/bash
set -euo pipefail

# GitHub Sync Script for AlphaMind Emissions Data
# Uploads emissions data directly to the alphamind GitHub repository

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

# Load environment variables
if [ -f secrets/.env ]; then
    source secrets/.env
fi

# Configuration
DATE_STR=$(date -u '+%Y%m%d')
TIMESTAMP=$(date -u '+%Y%m%d_%H%M%S')
EMISSIONS_DIR="emissions-data"
BRANCH_NAME="emissions-data-updates"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $*"
}

log "🔄 Starting GitHub sync for AlphaMind emissions data"
log "📅 Date: $DATE_STR"
log "🕐 Timestamp: $TIMESTAMP"

# Ensure we're in the right directory and have git configured
if [ ! -d ".git" ]; then
    log "ERROR: Not in a git repository"
    exit 1
fi

# Check if we have emissions data to upload
if [ ! -f "out/emissions_latest.json" ]; then
    log "ERROR: No emissions data found at out/emissions_latest.json"
    exit 1
fi

# Create emissions-data directory structure if it doesn't exist
mkdir -p "$EMISSIONS_DIR/daily"
mkdir -p "$EMISSIONS_DIR/secure"
mkdir -p "$EMISSIONS_DIR/manifests"

log "📦 Preparing emissions data for GitHub upload..."

# Copy latest emissions data to daily folder
cp "out/emissions_latest.json" "$EMISSIONS_DIR/daily/emissions_${DATE_STR}.json"
cp "out/emissions_latest.json" "$EMISSIONS_DIR/daily/emissions_latest.json"

# Copy secure data if available
if [ -d "out/secure" ]; then
    log "🔒 Copying secure emissions data..."
    # Copy the latest secure data
    if [ -f "out/secure/secure_data/latest_emissions_secure.json" ]; then
        cp "out/secure/secure_data/latest_emissions_secure.json" "$EMISSIONS_DIR/secure/emissions_secure_${DATE_STR}.json"
        cp "out/secure/secure_data/latest_emissions_secure.json" "$EMISSIONS_DIR/secure/latest_emissions_secure.json"
    fi
    
    # Copy integrity data
    if [ -d "out/secure/integrity" ]; then
        mkdir -p "$EMISSIONS_DIR/secure/integrity"
        cp -r "out/secure/integrity/"* "$EMISSIONS_DIR/secure/integrity/" 2>/dev/null || true
    fi
fi

# Copy manifests if available
if [ -d "manifests" ]; then
    log "📋 Copying manifest files..."
    cp manifests/*.json "$EMISSIONS_DIR/manifests/" 2>/dev/null || true
fi

# Create a summary file for this collection
cat > "$EMISSIONS_DIR/daily/collection_${DATE_STR}_summary.json" << EOF
{
    "collection_date": "$(date -u '+%Y-%m-%d')",
    "collection_timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "collection_method": "automated_daily_btcli",
    "files_created": [
        "emissions_${DATE_STR}.json",
        "emissions_secure_${DATE_STR}.json"
    ],
    "data_location": "emissions-data/daily/",
    "verification": "Cryptographically signed with SHA-256 + HMAC",
    "next_collection": "$(date -u -v+1d '+%Y-%m-%dT16:00:00Z')"
}
EOF

# Count total subnets from the data
SUBNET_COUNT=$(python3 -c "
import json
try:
    with open('$EMISSIONS_DIR/daily/emissions_${DATE_STR}.json') as f:
        data = json.load(f)
    print(data.get('total_subnets', 'unknown'))
except:
    print('unknown')
")

log "📊 Collection summary: $SUBNET_COUNT subnets collected"

# Check git status and prepare for commit
log "🔍 Checking git status..."

# Stash any uncommitted changes to avoid conflicts
if ! git diff --quiet || ! git diff --cached --quiet; then
    log "⚠️  Stashing uncommitted changes..."
    git stash push -m "Auto-stash before emissions data upload - $TIMESTAMP"
fi

# Switch to main branch and pull latest
log "🔄 Switching to main branch and pulling latest changes..."
git checkout main
git pull origin main

# Create or switch to emissions data branch
log "🌿 Creating/switching to emissions data branch..."
if git branch | grep -q "$BRANCH_NAME"; then
    git checkout "$BRANCH_NAME"
    git rebase main
else
    git checkout -b "$BRANCH_NAME"
fi

# Add the new emissions data
log "📝 Adding emissions data to git..."
git add "$EMISSIONS_DIR/"

# Check if there are changes to commit
if git diff --cached --quiet; then
    log "ℹ️  No new emissions data to commit"
    git checkout main
    exit 0
fi

# Commit the changes
COMMIT_MESSAGE="Add emissions data for $DATE_STR

- Collected $SUBNET_COUNT subnets at $(date -u '+%Y-%m-%d %H:%M UTC')
- Includes daily snapshot and secure cryptographically signed data
- Collection method: automated btcli via AlphaMind system
- Data stored in emissions-data/ for transparency

Files added:
- emissions-data/daily/emissions_${DATE_STR}.json
- emissions-data/secure/emissions_secure_${DATE_STR}.json
- emissions-data/daily/collection_${DATE_STR}_summary.json"

log "💾 Committing emissions data..."
git commit -m "$COMMIT_MESSAGE"

# Push to GitHub
log "⬆️  Pushing to GitHub..."
git push origin "$BRANCH_NAME"

# Create or update pull request (requires gh CLI)
if command -v gh >/dev/null 2>&1; then
    log "🔄 Creating/updating pull request..."
    
    PR_TITLE="Daily Emissions Data Update - $DATE_STR"
    PR_BODY="Automated daily emissions data collection for $(date -u '+%Y-%m-%d').

## Collection Summary
- **Date**: $(date -u '+%Y-%m-%d %H:%M UTC')
- **Subnets**: $SUBNET_COUNT
- **Network**: Bittensor Finney
- **Method**: Automated btcli collection

## Files Added
- \`emissions-data/daily/emissions_${DATE_STR}.json\` - Daily emissions snapshot
- \`emissions-data/secure/emissions_secure_${DATE_STR}.json\` - Cryptographically secured data
- \`emissions-data/daily/collection_${DATE_STR}_summary.json\` - Collection metadata

## Verification
All data is cryptographically signed with SHA-256 hashes and HMAC verification for integrity.

## Next Collection
Next automated collection: $(date -u -v+1d '+%Y-%m-%dT16:00:00Z')

---
*This PR was automatically generated by the AlphaMind emissions collection system.*"

    # Check if PR already exists
    if gh pr list --head "$BRANCH_NAME" --json number --jq '.[0].number' | grep -q .; then
        log "🔄 Updating existing pull request..."
        gh pr edit "$BRANCH_NAME" --title "$PR_TITLE" --body "$PR_BODY"
    else
        log "🆕 Creating new pull request..."
        gh pr create --title "$PR_TITLE" --body "$PR_BODY" --base main --head "$BRANCH_NAME"
    fi
    
    PR_URL=$(gh pr list --head "$BRANCH_NAME" --json url --jq '.[0].url')
    log "🔗 Pull request: $PR_URL"
else
    log "⚠️  gh CLI not available - manual PR creation required"
    log "🔗 Branch pushed: https://github.com/alexlange1/alphamind/tree/$BRANCH_NAME"
fi

# Switch back to main
git checkout main

# Generate public URLs for transparency
GITHUB_BASE="https://github.com/alexlange1/alphamind/tree/$BRANCH_NAME"
DATA_URL="$GITHUB_BASE/emissions-data/daily/emissions_${DATE_STR}.json"
SECURE_URL="$GITHUB_BASE/emissions-data/secure/emissions_secure_${DATE_STR}.json"

log "🔗 Public URLs:"
log "   Daily Data: $DATA_URL"
log "   Secure Data: $SECURE_URL"

# Save URLs for reference
mkdir -p logs
cat > "logs/github_urls_$(date -u '+%Y%m%d').json" << EOF
{
    "date": "$DATE_STR",
    "timestamp": "$TIMESTAMP",
    "daily_data_url": "$DATA_URL",
    "secure_data_url": "$SECURE_URL",
    "branch": "$BRANCH_NAME",
    "repository": "https://github.com/alexlange1/alphamind",
    "subnet_count": "$SUBNET_COUNT",
    "collection_time": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF

log "✅ GitHub sync completed successfully"
log "📊 Summary: Emissions data for $SUBNET_COUNT subnets pushed to GitHub"
log "🌿 Branch: $BRANCH_NAME"

# Send Discord notification if configured
if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
    curl -H "Content-Type: application/json" \
         -X POST \
         -d "{\"embeds\": [{\"title\": \"✅ AlphaMind Emissions Data Uploaded\", \"description\": \"Daily emissions collection completed successfully\\n\\n📅 **Date**: $DATE_STR\\n📊 **Subnets**: $SUBNET_COUNT\\n🌿 **Branch**: $BRANCH_NAME\\n🔗 **Data**: [View on GitHub]($DATA_URL)\", \"color\": 65280, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\"}]}" \
         "${DISCORD_WEBHOOK_URL}" || true
fi
