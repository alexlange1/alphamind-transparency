#!/bin/bash
# NAV Update Script - Runs every 10 minutes
# This script updates the NAV (Net Asset Value) for TAO20

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/nav_update.log"
ERROR_FILE="$SCRIPT_DIR/nav_update.err"
PYTHON_SCRIPT="$SCRIPT_DIR/update_nav.py"

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

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    log_error "Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Check if Python script is executable
if [ ! -x "$PYTHON_SCRIPT" ]; then
    chmod +x "$PYTHON_SCRIPT"
fi

# Run NAV update
log_message "Starting NAV update"
if python3 "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>> "$ERROR_FILE"; then
    log_message "NAV update completed successfully"
else
    log_error "NAV update failed with exit code $?"
    exit 1
fi

