#!/usr/bin/env bash
# backup.sh: DB backup script for Vapi Platform
# Uses Cloudflare R2 (S3-compatible) for remote storage.
set -euo pipefail

# Load environment variables if .env file exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

DB_USER=${DB_USER:-postgres}
DB_NAME=${DB_NAME:-vapi_platform}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "=== Starting DB Backup for database: $DB_NAME ==="

# Run pg_dump via Docker Compose inside the db container
docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"

echo "Backup created successfully at: $BACKUP_FILE"
echo "Size: $(du -sh "$BACKUP_FILE" | cut -f1)"

# Check if Cloudflare R2 integration is configured
# R2 endpoint format: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
if [ -n "${R2_BUCKET:-}" ] && [ -n "${R2_ACCESS_KEY_ID:-}" ] && [ -n "${R2_SECRET_ACCESS_KEY:-}" ] && [ -n "${R2_ACCOUNT_ID:-}" ]; then
  R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
  echo "Uploading backup to Cloudflare R2 bucket: $R2_BUCKET..."

  # Use AWS CLI with R2 endpoint (R2 is S3-compatible)
  docker run --rm \
    -e AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
    -e AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
    -e AWS_DEFAULT_REGION="auto" \
    -v "$(pwd)/backups:/backups" \
    amazon/aws-cli s3 cp "/backups/backup_$TIMESTAMP.sql.gz" \
      "s3://$R2_BUCKET/backups/backup_$TIMESTAMP.sql.gz" \
      --endpoint-url "$R2_ENDPOINT"

  echo "Backup successfully uploaded to Cloudflare R2!"
else
  echo "R2 credentials/bucket not fully specified. Retaining local backup only."
fi

echo "=== Backup Process Complete ==="
