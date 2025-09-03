#!/bin/bash
set -euo pipefail

# S3 Sync Script for AlphaMind Emissions Data
# Uploads secure data and manifests to S3 with versioning

# Load environment variables
if [ -f secrets/.env ]; then
    source secrets/.env
fi

# Validate required environment variables
: "${S3_BUCKET:?S3_BUCKET environment variable is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID environment variable is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY environment variable is required}"

# Configuration
DATE_STR=$(date -u '+%Y/%m/%d')
TIMESTAMP=$(date -u '+%Y%m%d_%H%M%S')
S3_PREFIX="emissions"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $*"
}

log "☁️  Starting S3 sync for AlphaMind emissions data"
log "S3 Bucket: s3://$S3_BUCKET"
log "Date path: $DATE_STR"

# Ensure AWS CLI is configured
aws configure set default.region "$REGION"

# Verify S3 bucket exists and is accessible
log "🔍 Verifying S3 bucket access..."
if ! aws s3 ls "s3://$S3_BUCKET/" > /dev/null; then
    log "ERROR: Cannot access S3 bucket s3://$S3_BUCKET"
    log "Please check:"
    log "  - Bucket exists and is accessible"
    log "  - AWS credentials are correct"
    log "  - Bucket region matches AWS_DEFAULT_REGION ($REGION)"
    exit 1
fi

# Check if versioning is enabled
VERSIONING=$(aws s3api get-bucket-versioning --bucket "$S3_BUCKET" --query 'Status' --output text 2>/dev/null || echo "None")
if [ "$VERSIONING" != "Enabled" ]; then
    log "⚠️  WARNING: S3 bucket versioning is not enabled"
    log "   Enable versioning for immutable data history:"
    log "   aws s3api put-bucket-versioning --bucket $S3_BUCKET --versioning-configuration Status=Enabled"
fi

# Create temporary staging directory
STAGING_DIR=$(mktemp -d)
trap "rm -rf $STAGING_DIR" EXIT

log "📦 Preparing data for upload..."

# Copy secure data with proper structure
mkdir -p "$STAGING_DIR/$S3_PREFIX/$DATE_STR"
cp -r out/secure/ "$STAGING_DIR/$S3_PREFIX/$DATE_STR/"

# Copy manifests
mkdir -p "$STAGING_DIR/manifests/$DATE_STR"
cp manifests/manifest_*.json "$STAGING_DIR/manifests/$DATE_STR/" 2>/dev/null || true

# Copy latest manifest to root for easy access
cp manifests/manifest_latest.json "$STAGING_DIR/manifests/" 2>/dev/null || true

# Set proper permissions (readable by owner only)
find "$STAGING_DIR" -type f -exec chmod 600 {} \;
find "$STAGING_DIR" -type d -exec chmod 700 {} \;

# Calculate total size
TOTAL_SIZE=$(du -sh "$STAGING_DIR" | cut -f1)
log "📊 Total data size: $TOTAL_SIZE"

# Upload to S3 with server-side encryption
log "⬆️  Uploading to S3..."

# Upload emissions data
aws s3 sync "$STAGING_DIR/$S3_PREFIX/" "s3://$S3_BUCKET/$S3_PREFIX/" \
    --delete \
    --exact-timestamps \
    --server-side-encryption AES256 \
    --metadata "collection-date=$DATE_STR,upload-time=$TIMESTAMP"

# Upload manifests
aws s3 sync "$STAGING_DIR/manifests/" "s3://$S3_BUCKET/manifests/" \
    --delete \
    --exact-timestamps \
    --server-side-encryption AES256 \
    --metadata "collection-date=$DATE_STR,upload-time=$TIMESTAMP"

# Verify upload by listing today's files
log "🔍 Verifying upload..."
UPLOADED_COUNT=$(aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/$DATE_STR/" --recursive | wc -l)
LOCAL_COUNT=$(find "$STAGING_DIR/$S3_PREFIX/$DATE_STR" -type f | wc -l)

if [ "$UPLOADED_COUNT" -eq "$LOCAL_COUNT" ]; then
    log "✅ Upload verified: $UPLOADED_COUNT files uploaded successfully"
else
    log "❌ Upload verification failed: $UPLOADED_COUNT uploaded vs $LOCAL_COUNT local files"
    exit 1
fi

# Set lifecycle policy for cost optimization (if not already set)
LIFECYCLE_EXISTS=$(aws s3api get-bucket-lifecycle-configuration --bucket "$S3_BUCKET" 2>/dev/null || echo "none")
if [ "$LIFECYCLE_EXISTS" = "none" ]; then
    log "📋 Setting up S3 lifecycle policy for cost optimization..."
    
    cat > /tmp/lifecycle.json << EOF
{
    "Rules": [
        {
            "ID": "AlphaMindEmissionsLifecycle",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "emissions/"
            },
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                },
                {
                    "Days": 365,
                    "StorageClass": "DEEP_ARCHIVE"
                }
            ],
            "NoncurrentVersionTransitions": [
                {
                    "NoncurrentDays": 7,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "NoncurrentDays": 30,
                    "StorageClass": "GLACIER"
                }
            ]
        }
    ]
}
EOF
    
    aws s3api put-bucket-lifecycle-configuration \
        --bucket "$S3_BUCKET" \
        --lifecycle-configuration file:///tmp/lifecycle.json
    
    rm /tmp/lifecycle.json
    log "✅ Lifecycle policy configured for cost optimization"
fi

# Generate public S3 URLs for transparency
MANIFEST_URL="https://$S3_BUCKET.s3.amazonaws.com/manifests/manifest_latest.json"
DATA_URL="https://$S3_BUCKET.s3.amazonaws.com/$S3_PREFIX/$DATE_STR/"

log "🔗 Public URLs:"
log "   Manifest: $MANIFEST_URL"
log "   Data: $DATA_URL"

# Save URLs for transparency repo
mkdir -p logs
cat > "logs/s3_urls_$(date -u '+%Y%m%d').json" << EOF
{
    "date": "$DATE_STR",
    "timestamp": "$TIMESTAMP",
    "manifest_url": "$MANIFEST_URL",
    "data_url": "$DATA_URL",
    "bucket": "$S3_BUCKET",
    "total_size": "$TOTAL_SIZE",
    "file_count": $UPLOADED_COUNT
}
EOF

log "✅ S3 sync completed successfully"
log "📊 Summary: $UPLOADED_COUNT files ($TOTAL_SIZE) uploaded to s3://$S3_BUCKET"
