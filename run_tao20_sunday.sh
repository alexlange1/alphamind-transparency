#!/bin/bash
set -euo pipefail

# Load environment variables
source /opt/alphamind/src/secrets/.env

# Change to project directory  
cd /opt/alphamind/src

# Activate virtual environment
source /opt/alphamind/venv/bin/activate

# Export AWS credentials for the subprocess
export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY
export AWS_DEFAULT_REGION
export S3_BUCKET
export PYTHONPATH="/opt/alphamind/src"

# Run the TAO20 Sunday publisher
exec python3 scripts/tao20_sunday_publisher.py
