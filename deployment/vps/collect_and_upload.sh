#!/bin/bash
set -euo pipefail

# AlphaMind Emissions Collection and Upload Script
# Runs daily via systemd timer

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

# Source environment variables
if [ -f secrets/.env ]; then
    source secrets/.env
fi

# Logging setup
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/emissions_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $*" | tee -a "$LOG_FILE"
}

# Function to send Discord notification
send_discord_notification() {
    local status="$1"
    local message="$2"
    
    if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
        local color="65280"  # Green
        if [ "$status" = "ERROR" ]; then
            color="16711680"  # Red
        elif [ "$status" = "WARNING" ]; then
            color="16776960"  # Yellow
        fi
        
        curl -H "Content-Type: application/json" \
             -X POST \
             -d "{\"embeds\": [{\"title\": \"AlphaMind Emissions Collection\", \"description\": \"$message\", \"color\": $color, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\"}]}" \
             "${DISCORD_WEBHOOK_URL}" || true
    fi
}

# Error handler
handle_error() {
    local exit_code=$?
    local line_number=$1
    log "ERROR: Script failed at line $line_number with exit code $exit_code"
    send_discord_notification "ERROR" "❌ Emissions collection failed at line $line_number (exit code: $exit_code)"
    exit $exit_code
}

trap 'handle_error $LINENO' ERR

log "🚀 Starting AlphaMind emissions collection"
log "Project root: $PROJECT_ROOT"
log "Python path: $(which python3)"
log "btcli path: $(which btcli)"

# Activate virtual environment
source venv/bin/activate

# Verify btcli is working
log "🔍 Verifying btcli connection..."
timeout 30 btcli --help > /dev/null || {
    log "ERROR: btcli not responding"
    send_discord_notification "ERROR" "❌ btcli not responding or not installed"
    exit 1
}

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT"
export BITTENSOR_NETWORK="${BITTENSOR_NETWORK:-finney}"
export ALPHAMIND_SECRET_KEY="${ALPHAMIND_SECRET_KEY:-}"

# Create timestamp for this collection
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
DATE_STR=$(date -u '+%Y%m%d')

log "📊 Collecting emissions data for $TIMESTAMP"

# Run the secure emissions collection
log "🔒 Running secure emissions collection..."
python3 scripts/daily_emissions_collection.py 2>&1 | tee -a "$LOG_FILE"

# Verify collection succeeded
LATEST_FILE="data/secure/secure_data/latest_emissions_secure.json"
if [ ! -f "$LATEST_FILE" ]; then
    log "ERROR: No latest emissions file found at $LATEST_FILE"
    send_discord_notification "ERROR" "❌ Emissions collection failed - no data file generated"
    exit 1
fi

# Extract collection stats
SUBNET_COUNT=$(python3 -c "
import json
with open('$LATEST_FILE') as f:
    data = json.load(f)
print(data.get('total_subnets', 0))
")

log "✅ Collection completed: $SUBNET_COUNT subnets"

# Generate cryptographic manifest
log "📝 Generating cryptographic manifest..."
python3 deployment/vps/generate_manifest.py

# Upload to S3 with versioning
log "☁️  Uploading to S3..."
bash deployment/vps/s3_sync.sh

# Verify upload
log "🔍 Verifying S3 upload..."
aws s3 ls "s3://${S3_BUCKET}/emissions/$(date -u '+%Y/%m/%d')/" || {
    log "ERROR: S3 upload verification failed"
    send_discord_notification "ERROR" "❌ S3 upload failed or verification failed"
    exit 1
}

# Update transparency repo
log "📋 Updating transparency repository..."
bash deployment/vps/update_transparency.sh

# Clean up old local files (keep last 7 days)
log "🧹 Cleaning up old files..."
find logs/ -name "emissions_*.log" -mtime +7 -delete 2>/dev/null || true
find data/secure/secure_data/ -name "emissions_secure_*.json" -mtime +7 -delete 2>/dev/null || true
find data/secure/backups/ -name "emissions_secure_*.json" -mtime +7 -delete 2>/dev/null || true

# Final status
TOTAL_SIZE=$(du -sh data/secure/ | cut -f1)
log "✅ Collection completed successfully"
log "📊 Stats: $SUBNET_COUNT subnets, $TOTAL_SIZE total data"

# Send success notification
send_discord_notification "SUCCESS" "✅ Daily emissions collection completed successfully\\n📊 $SUBNET_COUNT subnets collected\\n💾 $TOTAL_SIZE data stored\\n⏰ Collection time: $TIMESTAMP"

log "🎯 AlphaMind emissions collection finished"
