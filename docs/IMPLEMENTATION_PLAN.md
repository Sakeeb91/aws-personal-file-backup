# Implementation Plan: AWS Personal File Backup

## Expert Role: Cloud/DevOps Engineer

This project requires expertise in AWS infrastructure (S3, Lambda, SNS, IAM, CloudTrail), Infrastructure as Code (SAM/CloudFormation), and event-driven architecture patterns. The Cloud/DevOps Engineer role is optimal because:

- Deep understanding of AWS service integrations and IAM permissions
- Experience with serverless event-driven architectures
- Knowledge of IaC best practices and deployment strategies
- Security-first mindset for production-ready infrastructure

---

## System Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AWS ACCOUNT                                         │
│                                                                                  │
│  ┌──────────────┐                                        ┌──────────────┐       │
│  │              │                                        │              │       │
│  │   CloudTrail │◄───────────────────────────────────────┤   S3 Logs    │       │
│  │   (Optional) │         Data Event Logging             │   Bucket     │       │
│  │              │                                        │              │       │
│  └──────────────┘                                        └──────────────┘       │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         CORE PIPELINE                                     │   │
│  │                                                                           │   │
│  │   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │   │
│  │   │              │     │              │     │              │            │   │
│  │   │    Source    │────►│    Lambda    │────►│    Backup    │            │   │
│  │   │    Bucket    │     │   Function   │     │    Bucket    │            │   │
│  │   │   (inbox)    │     │              │     │              │            │   │
│  │   │              │     │              │     │              │            │   │
│  │   │ • Versioning │     │ FileBackup   │     │ • Versioning │            │   │
│  │   │ • SSE-S3     │     │ Handler      │     │ • SSE-S3     │            │   │
│  │   │ • Block Pub  │     │              │     │ • Block Pub  │            │   │
│  │   └──────────────┘     └──────┬───────┘     └──────────────┘            │   │
│  │          │                    │                                          │   │
│  │          │ S3 Event           │ Publish                                  │   │
│  │          │ ObjectCreated      │                                          │   │
│  │          ▼                    ▼                                          │   │
│  │   ┌──────────────┐     ┌──────────────┐                                 │   │
│  │   │   S3 Event   │     │              │                                 │   │
│  │   │ Notification │     │  SNS Topic   │────► Email Notification         │   │
│  │   │              │     │              │                                 │   │
│  │   └──────────────┘     └──────────────┘                                 │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         SUPPORTING SERVICES                               │   │
│  │                                                                           │   │
│  │   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │   │
│  │   │              │     │              │     │              │            │   │
│  │   │     IAM      │     │  CloudWatch  │     │     SAM      │            │   │
│  │   │    Role      │     │    Logs      │     │  Template    │            │   │
│  │   │              │     │              │     │              │            │   │
│  │   │ LambdaBackup │     │ /aws/lambda/ │     │ template.yaml│            │   │
│  │   │ Role         │     │ FileBackup   │     │              │            │   │
│  │   │              │     │ Handler      │     │              │            │   │
│  │   └──────────────┘     └──────────────┘     └──────────────┘            │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. User uploads file ──► Source Bucket (s3://inbox-bucket/file.pdf)
                              │
                              ▼
2. S3 generates ObjectCreated event
                              │
                              ▼
3. Lambda triggered with event payload:
   {
     "Records": [{
       "s3": {
         "bucket": {"name": "inbox-bucket"},
         "object": {"key": "file.pdf", "size": 1024}
       }
     }]
   }
                              │
                              ▼
4. Lambda executes:
   a. Extract bucket/key from event
   b. Copy object to backup bucket
   c. Publish SNS notification
   d. Log result to CloudWatch
                              │
                              ▼
5. User receives email: "File 'file.pdf' backed up successfully"
```

---

## Technology Selection

| Component | Technology | Rationale | Tradeoffs | Fallback |
|-----------|------------|-----------|-----------|----------|
| Runtime | Python 3.9 | Junior-friendly, boto3 native | Slower cold starts than Go | Python 3.8 |
| IaC | SAM | Simplified Lambda deployment | Less flexible than Terraform | CloudFormation |
| Storage | S3 | Native event triggers | Egress costs at scale | N/A |
| Compute | Lambda | Pay-per-use, event-driven | 15min timeout, cold starts | EC2 (not recommended) |
| Notifications | SNS | Simple email delivery | No rich formatting | SES (more complex) |
| Monitoring | CloudWatch | Native AWS integration | Query costs at scale | N/A |
| Audit | CloudTrail | Compliance, debugging | Additional costs | S3 access logs |

### Design Patterns

| Pattern | Application | Benefit |
|---------|-------------|---------|
| Event-Driven | S3 → Lambda trigger | Decoupled, scalable |
| Fan-Out | SNS topic | Multiple subscribers possible |
| Least Privilege | IAM inline policies | Security hardening |
| Infrastructure as Code | SAM template | Reproducible deployments |
| Idempotency | Skip duplicate copies | Prevents duplicate backups |

---

## Phased Implementation Plan

### Phase 1: Infrastructure Foundation (Core Buckets + IAM)

**Objective:** Create the foundational AWS resources with proper security configuration.

**Scope:**
- `template.yaml` - SAM template with S3 buckets and IAM role
- Two S3 buckets with versioning, encryption, and public access blocking
- IAM role with least-privilege permissions

**Deliverables:**
| Deliverable | Verification Method |
|-------------|-------------------|
| template.yaml | `sam validate` passes |
| Source bucket | `aws s3 ls` shows bucket |
| Backup bucket | `aws s3 ls` shows bucket |
| IAM role | `aws iam get-role` returns role |

**Code Skeleton:**

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Personal File Backup System

Parameters:
  SourceBucketName:
    Type: String
    Description: Name for the source (inbox) bucket
  BackupBucketName:
    Type: String
    Description: Name for the backup bucket
  NotificationEmail:
    Type: String
    Description: Email address for backup notifications

Resources:
  SourceBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref SourceBucketName
      VersioningConfiguration:
        Status: Enabled
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  BackupBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BackupBucketName
      VersioningConfiguration:
        Status: Enabled
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
```

**Technical Challenges:**
- Bucket names must be globally unique - use account ID or random suffix
- IAM policy syntax errors are cryptic - validate with IAM policy simulator

**Definition of Done:**
- [ ] `sam validate` returns no errors
- [ ] `sam deploy` creates both buckets
- [ ] Buckets have versioning enabled (verify in console)
- [ ] Buckets have SSE-S3 encryption (verify in console)
- [ ] Public access is blocked (verify in console)

---

### Phase 2: Lambda Function (Core Logic)

**Objective:** Implement the file copy logic with proper error handling and logging.

**Scope:**
- `src/lambda/file_backup_handler.py` - Main Lambda handler
- Environment variables configuration
- CloudWatch logging integration

**Deliverables:**
| Deliverable | Verification Method |
|-------------|-------------------|
| Lambda handler | Unit tests pass |
| CloudWatch logs | Logs appear after invocation |
| Copy functionality | File appears in backup bucket |

**Code Skeleton:**

```python
# src/lambda/file_backup_handler.py
import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')

# Environment variables
BACKUP_BUCKET = os.environ.get('BACKUP_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')


def handler(event, context):
    """
    Lambda handler for S3 ObjectCreated events.
    Copies uploaded files to backup bucket and sends SNS notification.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    for record in event.get('Records', []):
        try:
            # Extract S3 event details
            source_bucket = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']
            object_size = record['s3']['object'].get('size', 0)

            logger.info(f"Processing: s3://{source_bucket}/{object_key}")

            # Copy to backup bucket
            copy_source = {'Bucket': source_bucket, 'Key': object_key}
            s3_client.copy_object(
                CopySource=copy_source,
                Bucket=BACKUP_BUCKET,
                Key=object_key
            )

            logger.info(f"Copied to: s3://{BACKUP_BUCKET}/{object_key}")

            # Send SNS notification
            if SNS_TOPIC_ARN:
                message = {
                    'event': 'copied',
                    'source': f"s3://{source_bucket}/{object_key}",
                    'destination': f"s3://{BACKUP_BUCKET}/{object_key}",
                    'size_bytes': object_size
                }
                sns_client.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject=f"File Backed Up: {object_key}",
                    Message=json.dumps(message, indent=2)
                )
                logger.info(f"SNS notification sent")

        except ClientError as e:
            logger.error(f"AWS error: {e.response['Error']['Message']}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Backup complete'})
    }
```

**Technical Challenges:**
- URL-encoded object keys (spaces become `+` or `%20`)
- Large files (>5GB) require multipart copy
- Lambda timeout for very large files

**Definition of Done:**
- [ ] Lambda deploys successfully
- [ ] Test file copied to backup bucket
- [ ] CloudWatch logs show "Copied to:" message
- [ ] No errors in CloudWatch logs

---

### Phase 3: SNS Integration (Notifications)

**Objective:** Set up SNS topic and email notifications with proper subscription confirmation.

**Scope:**
- SNS topic in template.yaml
- Email subscription
- Lambda SNS publish permissions

**Deliverables:**
| Deliverable | Verification Method |
|-------------|-------------------|
| SNS topic | `aws sns list-topics` shows topic |
| Email subscription | Confirmation email received |
| Lambda notification | Backup email received |

**Code Addition to template.yaml:**

```yaml
  NotificationTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub "${AWS::StackName}-backup-notifications"

  EmailSubscription:
    Type: AWS::SNS::Subscription
    Properties:
      TopicArn: !Ref NotificationTopic
      Protocol: email
      Endpoint: !Ref NotificationEmail
```

**Technical Challenges:**
- Email subscription requires manual confirmation
- SNS publish failures should not fail the backup

**Definition of Done:**
- [ ] SNS topic created
- [ ] Confirmation email received and confirmed
- [ ] Test upload triggers backup email
- [ ] Email contains file name and status

---

### Phase 4: S3 Event Trigger (Wiring)

**Objective:** Connect S3 events to Lambda function for automatic triggering.

**Scope:**
- S3 NotificationConfiguration in template.yaml
- Lambda resource-based policy for S3 invocation
- Event filtering for ObjectCreated

**Code Addition to template.yaml:**

```yaml
  FileBackupFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "${AWS::StackName}-FileBackupHandler"
      Handler: file_backup_handler.handler
      Runtime: python3.9
      CodeUri: src/lambda/
      Timeout: 60
      MemorySize: 256
      Environment:
        Variables:
          BACKUP_BUCKET: !Ref BackupBucketName
          SNS_TOPIC_ARN: !Ref NotificationTopic
      Policies:
        - S3ReadPolicy:
            BucketName: !Ref SourceBucketName
        - S3CrudPolicy:
            BucketName: !Ref BackupBucketName
        - SNSPublishMessagePolicy:
            TopicName: !GetAtt NotificationTopic.TopicName
      Events:
        S3Event:
          Type: S3
          Properties:
            Bucket: !Ref SourceBucket
            Events: s3:ObjectCreated:*
```

**Technical Challenges:**
- Circular dependency between S3 bucket and Lambda
- Permission timing issues during deployment

**Definition of Done:**
- [ ] S3 event trigger configured
- [ ] Upload to source bucket triggers Lambda
- [ ] File automatically appears in backup bucket
- [ ] Email notification received

---

### Phase 5: Testing and Validation

**Objective:** Implement comprehensive test suite covering all test matrix scenarios.

**Scope:**
- `tests/unit/test_handler.py` - Unit tests with mocked AWS services
- `tests/integration/test_e2e.py` - End-to-end tests
- `scripts/test_upload.sh` - Manual testing script

**Code Skeleton:**

```python
# tests/unit/test_handler.py
import json
import pytest
from unittest.mock import MagicMock, patch
import sys
sys.path.insert(0, 'src/lambda')

from file_backup_handler import handler


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


@patch('file_backup_handler.s3_client')
@patch('file_backup_handler.sns_client')
@patch.dict('os.environ', {
    'BACKUP_BUCKET': 'test-backup-bucket',
    'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789:test-topic'
})
def test_happy_path(mock_sns, mock_s3, s3_event):
    """Test successful file backup and notification."""
    result = handler(s3_event, None)

    assert result['statusCode'] == 200
    mock_s3.copy_object.assert_called_once()
    mock_sns.publish.assert_called_once()


@patch('file_backup_handler.s3_client')
@patch('file_backup_handler.sns_client')
@patch.dict('os.environ', {
    'BACKUP_BUCKET': 'test-backup-bucket',
    'SNS_TOPIC_ARN': ''
})
def test_no_sns_topic(mock_sns, mock_s3, s3_event):
    """Test backup works even without SNS configured."""
    result = handler(s3_event, None)

    assert result['statusCode'] == 200
    mock_s3.copy_object.assert_called_once()
    mock_sns.publish.assert_not_called()
```

**Definition of Done:**
- [ ] All unit tests pass (`pytest tests/unit/`)
- [ ] Test coverage > 80%
- [ ] All 8 test matrix scenarios validated
- [ ] No errors in CloudWatch logs

---

### Phase 6: CloudTrail Integration (Optional)

**Objective:** Enable audit logging for compliance and debugging.

**Scope:**
- CloudTrail trail configuration
- S3 data events for source bucket
- Log analysis queries

**Technical Challenges:**
- CloudTrail costs can add up with high volume
- Log delivery has 5-15 minute delay

**Definition of Done:**
- [ ] CloudTrail trail created
- [ ] S3 data events enabled
- [ ] Upload event visible in trail logs

---

## Risk Assessment

| Risk | Likelihood | Impact | Early Warning | Mitigation |
|------|------------|--------|---------------|------------|
| Lambda timeout on large files | Medium | 🟡 | Files >100MB | Increase timeout to 5min; use multipart copy |
| Bucket name collision | High | 🔴 | Deploy fails | Use account ID suffix in bucket names |
| SNS email not confirmed | Medium | 🟡 | No emails received | Add manual verification step in docs |
| IAM permission denied | Medium | 🔴 | Lambda errors | Test with minimal permissions first |
| S3 event duplicates | Low | 🟢 | Multiple copies | Implement idempotency check |
| Cost overrun | Low | 🟢 | CloudWatch billing alerts | Set up billing alerts at $1 threshold |

---

## Testing Strategy

### Test Pyramid

```
                    ┌─────────────┐
                    │   E2E (1)   │  Manual validation
                    ├─────────────┤
                    │Integration  │  Real AWS services
                    │    (3)      │
                    ├─────────────┤
                    │    Unit     │  Mocked services
                    │    (10+)    │
                    └─────────────┘
```

### First Three Tests to Write

1. **test_happy_path** - Verify file copy and SNS notification
2. **test_missing_env_vars** - Verify graceful handling of missing config
3. **test_s3_error_handling** - Verify proper error logging

### Testing Framework

- **pytest** - Test runner and fixtures
- **moto** - AWS service mocking
- **pytest-cov** - Coverage reporting

---

## First Concrete Task

### File to Create: `template.yaml`

**Location:** `/aws-personal-file-backup/template.yaml`

**First Function:** SAM template Parameters section

### Starter Code (Copy-Paste Ready)

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: >
  Personal File Backup System
  Event-driven backup pipeline using S3, Lambda, and SNS

Parameters:
  SourceBucketName:
    Type: String
    Description: Name for the source (inbox) bucket
    AllowedPattern: ^[a-z0-9][a-z0-9-]*[a-z0-9]$
    ConstraintDescription: Bucket name must be lowercase, alphanumeric, and hyphens only

  BackupBucketName:
    Type: String
    Description: Name for the backup bucket
    AllowedPattern: ^[a-z0-9][a-z0-9-]*[a-z0-9]$
    ConstraintDescription: Bucket name must be lowercase, alphanumeric, and hyphens only

  NotificationEmail:
    Type: String
    Description: Email address for backup notifications
    AllowedPattern: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
    ConstraintDescription: Must be a valid email address

Globals:
  Function:
    Timeout: 60
    Runtime: python3.9

# TODO: Add Resources section in next iteration
```

### Verification Method

```bash
sam validate --template template.yaml
```

Expected output: `template.yaml is a valid SAM Template`

### First Commit Message

```
feat(infra): Add SAM template with parameter definitions

- Define Parameters for bucket names and notification email
- Add input validation with regex patterns
- Set global Lambda configuration
```

---

## Learning Notes for Junior Developers

### Concepts to Understand Before Coding

1. **S3 Event Notifications** - How S3 triggers Lambda on object operations
2. **IAM Policies** - Difference between identity-based and resource-based policies
3. **CloudFormation Intrinsic Functions** - `!Ref`, `!Sub`, `!GetAtt`
4. **Lambda Environment Variables** - Externalize configuration
5. **boto3 Client vs Resource** - When to use each

### Recommended Reading

- [AWS SAM Developer Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/)
- [S3 Event Notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/NotificationHowTo.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

---

## Checklist Summary

### Core Checklist
- [ ] Source & backup buckets created (Block public, SSE-S3, Versioning)
- [ ] SNS topic created, email Confirmed
- [ ] IAM role `LambdaBackupRole` with logs + least-privilege inline policy
- [ ] Lambda `FileBackupHandler` deployed (env vars set)
- [ ] S3 event → Lambda wired on ObjectCreated
- [ ] Test upload copied to backup + SNS email received
- [ ] (Optional) CloudTrail data events enabled for source bucket

### Portfolio Deliverables
- [ ] Screenshot: Source bucket object + Backup bucket object
- [ ] Screenshot: CloudWatch log with `{"event":"copied"}`
- [ ] Screenshot: SNS "File Backed Up" email
- [ ] (Optional) CloudTrail event record snippet
- [ ] GitHub repo: Lambda code + README (architecture, steps, tests, costs, enhancements)
