#!/bin/bash
# Test the file backup system by uploading a test file

set -e

if [ -z "$1" ]; then
    echo "Usage: ./test_upload.sh <source-bucket-name>"
    exit 1
fi

SOURCE_BUCKET=$1
TEST_FILE="test-file-$(date +%s).txt"

echo "Creating test file: $TEST_FILE"
echo "Test file created at $(date)" > /tmp/$TEST_FILE

echo "Uploading to s3://$SOURCE_BUCKET/$TEST_FILE"
aws s3 cp /tmp/$TEST_FILE s3://$SOURCE_BUCKET/$TEST_FILE

echo "Upload complete!"
echo "Check your email for the backup notification."
echo "Verify backup with: aws s3 ls s3://<backup-bucket>/$TEST_FILE"

rm /tmp/$TEST_FILE
