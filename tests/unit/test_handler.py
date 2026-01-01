"""
Unit tests for the file backup Lambda handler.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add lambda source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/lambda'))


@pytest.fixture
def s3_event():
    """Sample S3 ObjectCreated event."""
    return {
        'Records': [{
            's3': {
                'bucket': {'name': 'test-source-bucket'},
                'object': {'key': 'test-file.pdf', 'size': 1024}
            }
        }]
    }


@pytest.fixture
def s3_event_url_encoded():
    """S3 event with URL-encoded key (spaces)."""
    return {
        'Records': [{
            's3': {
                'bucket': {'name': 'test-source-bucket'},
                'object': {'key': 'folder/my+file+name.pdf', 'size': 2048}
            }
        }]
    }


@pytest.fixture
def mock_env_vars():
    """Set up environment variables for tests."""
    return {
        'BACKUP_BUCKET': 'test-backup-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    }


class TestHappyPath:
    """Tests for successful backup scenarios."""

    @patch('file_backup_handler.s3_client')
    @patch('file_backup_handler.sns_client')
    def test_successful_backup_and_notification(self, mock_sns, mock_s3, s3_event, mock_env_vars):
        """Test successful file backup and SNS notification."""
        with patch.dict(os.environ, mock_env_vars):
            # Mock head_object to return 404 (object doesn't exist)
            mock_s3.head_object.side_effect = _create_not_found_error()

            from file_backup_handler import handler
            result = handler(s3_event, None)

            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['processed'] == 1
            assert body['errors'] == 0

            # Verify S3 copy was called
            mock_s3.copy_object.assert_called_once_with(
                CopySource={'Bucket': 'test-source-bucket', 'Key': 'test-file.pdf'},
                Bucket='test-backup-bucket',
                Key='test-file.pdf'
            )

            # Verify SNS publish was called
            mock_sns.publish.assert_called_once()

    @patch('file_backup_handler.s3_client')
    @patch('file_backup_handler.sns_client')
    def test_url_decoded_keys(self, mock_sns, mock_s3, s3_event_url_encoded, mock_env_vars):
        """Test that URL-encoded keys are properly decoded."""
        with patch.dict(os.environ, mock_env_vars):
            mock_s3.head_object.side_effect = _create_not_found_error()

            from file_backup_handler import handler
            result = handler(s3_event_url_encoded, None)

            assert result['statusCode'] == 200

            # Verify the key was decoded (+ becomes space)
            mock_s3.copy_object.assert_called_once()
            call_args = mock_s3.copy_object.call_args
            assert call_args.kwargs['Key'] == 'folder/my file name.pdf'


class TestIdempotency:
    """Tests for duplicate handling."""

    @patch('file_backup_handler.s3_client')
    @patch('file_backup_handler.sns_client')
    def test_skip_existing_backup(self, mock_sns, mock_s3, s3_event, mock_env_vars):
        """Test that existing backups are skipped."""
        with patch.dict(os.environ, mock_env_vars):
            # Mock head_object to succeed (object exists)
            mock_s3.head_object.return_value = {'ContentLength': 1024}

            from file_backup_handler import handler
            result = handler(s3_event, None)

            assert result['statusCode'] == 200

            # Verify copy was NOT called
            mock_s3.copy_object.assert_not_called()

            # Verify SNS was NOT called
            mock_sns.publish.assert_not_called()


class TestErrorHandling:
    """Tests for error scenarios."""

    @patch('file_backup_handler.s3_client')
    @patch('file_backup_handler.sns_client')
    def test_missing_backup_bucket_env(self, mock_sns, mock_s3, s3_event):
        """Test error when BACKUP_BUCKET env var is missing."""
        with patch.dict(os.environ, {'BACKUP_BUCKET': '', 'SNS_TOPIC_ARN': ''}):
            from file_backup_handler import handler

            with pytest.raises(ValueError, match="BACKUP_BUCKET"):
                handler(s3_event, None)

    @patch('file_backup_handler.s3_client')
    @patch('file_backup_handler.sns_client')
    def test_sns_failure_does_not_fail_backup(self, mock_sns, mock_s3, s3_event, mock_env_vars):
        """Test that SNS failure doesn't fail the overall backup."""
        with patch.dict(os.environ, mock_env_vars):
            mock_s3.head_object.side_effect = _create_not_found_error()
            mock_sns.publish.side_effect = Exception("SNS Error")

            from file_backup_handler import handler
            result = handler(s3_event, None)

            # Backup should still succeed
            assert result['statusCode'] == 200
            mock_s3.copy_object.assert_called_once()


class TestNoSNS:
    """Tests for scenarios without SNS configured."""

    @patch('file_backup_handler.s3_client')
    @patch('file_backup_handler.sns_client')
    def test_backup_without_sns_topic(self, mock_sns, mock_s3, s3_event):
        """Test backup works without SNS topic configured."""
        with patch.dict(os.environ, {'BACKUP_BUCKET': 'test-backup', 'SNS_TOPIC_ARN': ''}):
            mock_s3.head_object.side_effect = _create_not_found_error()

            from file_backup_handler import handler
            result = handler(s3_event, None)

            assert result['statusCode'] == 200
            mock_s3.copy_object.assert_called_once()
            mock_sns.publish.assert_not_called()


def _create_not_found_error():
    """Create a mock 404 ClientError."""
    from botocore.exceptions import ClientError
    return ClientError(
        {'Error': {'Code': '404', 'Message': 'Not Found'}},
        'HeadObject'
    )
