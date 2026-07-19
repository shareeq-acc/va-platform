#!/usr/bin/env bash
# restore.sh: DB restore script for Vapi Platform
# Uses Cloudflare R2 (S3-compatible) for remote storage.
set -euo pipefail

# Load environment variables if .env file exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

DB_USER=${DB_USER:-postgres}
DB_NAME=${DB_NAME:-vapi_platform}

if [ $# -lt 1 ]; then
  echo "Usage: $0 <path_to_backup_file_or_r2_uri>"
  echo "Examples:"
  echo "  $0 ./backups/backup_20260719_010000.sql.gz"
  echo "  $0 s3://my-r2-bucket/backups/backup_20260719_010000.sql.gz"
  exit 1
fi

TARGET=$1
LOCAL_FILE=""

# Check if target is an R2 URI (s3:// scheme works with aws CLI + endpoint-url)
if [[ "$TARGET" =~ ^s3:// ]]; then
  if [ -z "${R2_ACCESS_KEY_ID:-}" ] || [ -z "${R2_SECRET_ACCESS_KEY:-}" ] || [ -z "${R2_ACCOUNT_ID:-}" ]; then
    echo "Error: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ACCOUNT_ID must be set in .env to pull from R2."
    exit 1
  fi

  R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
  FILENAME=$(basename "$TARGET")
  LOCAL_FILE="./backups/downloaded_$FILENAME"
  mkdir -p ./backups

  echo "Downloading backup from Cloudflare R2: $TARGET -> $LOCAL_FILE..."
  docker run --rm \
    -e AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
    -e AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
    -e AWS_DEFAULT_REGION="auto" \
    -v "$(pwd)/backups:/backups" \
    amazon/aws-cli s3 cp "$TARGET" "/backups/downloaded_$FILENAME" \
      --endpoint-url "$R2_ENDPOINT"
else
  LOCAL_FILE="$TARGET"
fi

if [ ! -f "$LOCAL_FILE" ]; then
  echo "Error: Backup file does not exist at $LOCAL_FILE"
  exit 1
fi

echo "=== Starting DB Restore ==="
echo "Target DB: $DB_NAME"
echo "Source file: $LOCAL_FILE"

# Drop schema public and recreate to ensure clean state
echo "Recreating public schema..."
docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "Streaming restore dump into database container..."
gunzip -c "$LOCAL_FILE" | docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"

echo "=== Restore Process Complete ==="
