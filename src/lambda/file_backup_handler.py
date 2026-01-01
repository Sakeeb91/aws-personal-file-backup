"""
AWS Lambda handler for Personal File Backup System.

This function is triggered by S3 ObjectCreated events and:
1. Copies the uploaded file to a backup bucket
2. Sends an SNS notification about the backup
"""

import json
import logging
import os
import urllib.parse
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')

# Environment variables
BACKUP_BUCKET = os.environ.get('BACKUP_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')


def handler(event, context):
    """
    Lambda handler for S3 ObjectCreated events.

    Args:
        event: S3 event notification payload
        context: Lambda context object

    Returns:
        dict: Response with statusCode and body
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # Validate environment variables
    if not BACKUP_BUCKET:
        logger.error("BACKUP_BUCKET environment variable not set")
        raise ValueError("BACKUP_BUCKET environment variable is required")

    processed_count = 0
    error_count = 0

    for record in event.get('Records', []):
        try:
            # Extract S3 event details
            source_bucket = record['s3']['bucket']['name']
            # URL decode the object key (handles spaces and special characters)
            object_key = urllib.parse.unquote_plus(record['s3']['object']['key'])
            object_size = record['s3']['object'].get('size', 0)

            logger.info(f"Processing: s3://{source_bucket}/{object_key} ({object_size} bytes)")

            # Check if object already exists in backup (idempotency)
            if object_exists_in_backup(object_key):
                logger.info(f"skip_copy: Object already exists in backup: {object_key}")
                processed_count += 1
                continue

            # Copy object to backup bucket
            copy_object_to_backup(source_bucket, object_key)
            logger.info(f"Copied to: s3://{BACKUP_BUCKET}/{object_key}")

            # Send SNS notification
            send_notification(source_bucket, object_key, object_size)

            processed_count += 1
            logger.info(json.dumps({"event": "copied", "key": object_key}))

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS ClientError [{error_code}]: {error_message}")
            error_count += 1
            # Re-raise to trigger Lambda retry for transient errors
            if error_code in ['ServiceUnavailable', 'SlowDown', 'InternalError']:
                raise
        except Exception as e:
            logger.error(f"Unexpected error processing record: {str(e)}")
            error_count += 1

    response_body = {
        'message': 'Backup processing complete',
        'processed': processed_count,
        'errors': error_count
    }

    return {
        'statusCode': 200 if error_count == 0 else 207,
        'body': json.dumps(response_body)
    }


def object_exists_in_backup(object_key):
    """
    Check if an object already exists in the backup bucket.

    Args:
        object_key: The S3 object key to check

    Returns:
        bool: True if object exists, False otherwise
    """
    try:
        s3_client.head_object(Bucket=BACKUP_BUCKET, Key=object_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise


def copy_object_to_backup(source_bucket, object_key):
    """
    Copy an object from source bucket to backup bucket.

    Args:
        source_bucket: Source S3 bucket name
        object_key: The S3 object key to copy
    """
    copy_source = {
        'Bucket': source_bucket,
        'Key': object_key
    }

    s3_client.copy_object(
        CopySource=copy_source,
        Bucket=BACKUP_BUCKET,
        Key=object_key
    )


def send_notification(source_bucket, object_key, object_size):
    """
    Send an SNS notification about the backup.

    Args:
        source_bucket: Source S3 bucket name
        object_key: The backed up object key
        object_size: Size of the object in bytes
    """
    if not SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not configured, skipping notification")
        return

    try:
        message = {
            'event': 'copied',
            'source': f"s3://{source_bucket}/{object_key}",
            'destination': f"s3://{BACKUP_BUCKET}/{object_key}",
            'size_bytes': object_size
        }

        # Human-readable email body
        email_body = f"""File Backed Up Successfully

Source: s3://{source_bucket}/{object_key}
Backup: s3://{BACKUP_BUCKET}/{object_key}
Size: {format_size(object_size)}

This is an automated notification from your Personal File Backup system.
"""

        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"File Backed Up: {object_key}",
            Message=email_body,
            MessageAttributes={
                'event_type': {
                    'DataType': 'String',
                    'StringValue': 'file_backup'
                }
            }
        )
        logger.info("SNS notification sent successfully")

    except ClientError as e:
        # Log error but don't fail the backup
        logger.error(f"Failed to send SNS notification: {e.response['Error']['Message']}")


def format_size(size_bytes):
    """
    Format bytes into human-readable size string.

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Human-readable size (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"
