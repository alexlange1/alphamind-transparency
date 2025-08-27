#!/bin/bash
# Emissions Update Script (Simplified)
# This script currently runs NAV updates since emissions snapshot has import issues

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/emissions_update.log"
ERROR_FILE="$SCRIPT_DIR/emissions_update.err"
NAV_SCRIPT="$SCRIPT_DIR/update_nav.py"

# Ensure we're in the right directory
cd "$SCRIPT_DIR"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Function to log errors
log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: $1" >> "$ERROR_FILE"
}

# Check if NAV script exists
if [ ! -f "$NAV_SCRIPT" ]; then
    log_error "NAV script not found: $NAV_SCRIPT"
    exit 1
fi

# Run NAV update (temporary replacement for emissions)
log_message "Running NAV update (emissions snapshot temporarily disabled)"
if python3 "$NAV_SCRIPT" >> "$LOG_FILE" 2>> "$ERROR_FILE"; then
    log_message "NAV update completed successfully"
else
    log_error "NAV update failed with exit code $?"
    exit 1
fi
