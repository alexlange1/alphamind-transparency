#!/bin/bash
"""
Setup script for daily emissions collection cron job

This script sets up a portable cron job to run emissions collection daily at 4 PM UTC.
The cron job auto-detects the project location without requiring additional scripts.
"""

set -e

echo "Setting up portable daily emissions collection and TAO20 publication cron jobs..."

# Create portable cron job for daily emissions that finds alphamind project automatically
# This includes TAO20 publication check within the daily script (runs every Sunday when due)
DAILY_CRON_JOB='0 16 * * * bash -c '\''for dir in /opt/alphamind /home/alphamind/alphamind /Users/*/alphamind; do [ -f "$dir/deployment/vps/collect_and_upload.sh" ] && cd "$dir" && exec bash deployment/vps/collect_and_upload.sh >> logs/emissions_cron.log 2>&1; done'\'''

echo "Daily emissions cron job: $DAILY_CRON_JOB"

# Add to crontab (avoid duplicates)
(crontab -l 2>/dev/null | grep -v "collect_and_upload.sh\|alphamind-emissions-cron\|daily_emissions_collection.py\|tao20_sunday_publisher"; echo "$DAILY_CRON_JOB") | crontab -

echo "✅ Cron job installed successfully!"
echo "📊 Daily emissions collection: 4 PM UTC (16:00)"
echo "📈 TAO20 index publication: Automatic check every Sunday (publishes every 2 weeks)"
echo ""
echo "To verify the cron job is installed:"
echo "  crontab -l | grep collect_and_upload"
echo ""
echo "To view logs:"
echo "  tail -f logs/emissions_cron.log"
echo ""
echo "To remove the cron job:"
echo "  crontab -e  # and delete the line containing collect_and_upload.sh"
