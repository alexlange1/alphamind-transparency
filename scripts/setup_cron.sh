#!/bin/bash
"""
Setup script for daily emissions collection cron job

This script sets up a cron job to run emissions collection daily at 4 PM UTC.
"""

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_PATH="${PROJECT_ROOT}/venv/bin/python3"

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Warning: Virtual environment not found at $PYTHON_PATH"
    PYTHON_PATH="python3"
fi

# Create the cron job entry
CRON_JOB="0 16 * * * cd $PROJECT_ROOT && $PYTHON_PATH scripts/daily_emissions_collection.py >> logs/emissions_cron.log 2>&1"

echo "Setting up daily emissions collection cron job..."
echo "Cron job: $CRON_JOB"

# Add to crontab (avoid duplicates)
(crontab -l 2>/dev/null | grep -v "daily_emissions_collection.py"; echo "$CRON_JOB") | crontab -

echo "✅ Cron job installed successfully!"
echo "Emissions will be collected daily at 4 PM UTC (16:00)"
echo ""
echo "To verify the cron job is installed:"
echo "  crontab -l | grep emissions"
echo ""
echo "To view logs:"
echo "  tail -f logs/emissions_cron.log"
echo ""
echo "To remove the cron job:"
echo "  crontab -e  # and delete the line containing daily_emissions_collection.py"
