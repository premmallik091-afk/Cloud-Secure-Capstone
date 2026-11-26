#!/bin/bash
# Logical backup of the RDS database to S3 (supplements RDS automated backups).
# Needs: /etc/capstone.env, IAM role with s3:PutObject on the bucket, S3_BUCKET env var.
set -euo pipefail
source /etc/capstone.env
STAMP=$(date +%F-%H%M)
FILE=/tmp/capstone-$STAMP.sql.gz
mysqldump --single-transaction --ssl-ca="$DB_SSL_CA" -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" | gzip > "$FILE"
aws s3 cp "$FILE" "s3://${S3_BUCKET}/backups/" --sse AES256
rm -f "$FILE"
echo "Backup $STAMP uploaded"
