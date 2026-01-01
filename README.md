# AWS Personal File Backup

An event-driven backup pipeline on AWS that automatically copies files from an S3 inbox bucket to a backup bucket, sends SNS email notifications, and optionally logs activity via CloudTrail.

## Overview

This project implements a Dropbox-style personal backup system using AWS Free Tier services. When you upload a file to the source bucket, a Lambda function automatically copies it to a backup bucket and sends you an email confirmation.

**Analogy:** "Upload once, backed up automatically + you get a receipt."

## Architecture

```
                                    +------------------+
                                    |   CloudTrail     |
                                    |   (Optional)     |
                                    +--------+---------+
                                             |
                                             | Audit Logs
                                             v
+------------------+    S3 Event    +------------------+    Copy Object    +------------------+
|                  |  ObjectCreated |                  |                   |                  |
|  Source Bucket   +--------------->+     Lambda       +------------------>+  Backup Bucket   |
|  (inbox)         |                | FileBackupHandler|                   |  (backup)        |
|                  |                |                  |                   |                  |
+------------------+                +--------+---------+                   +------------------+
                                             |
                                             | Publish
                                             v
                                    +------------------+
                                    |    SNS Topic     |
                                    |                  |
                                    +--------+---------+
                                             |
                                             | Email
                                             v
                                    +------------------+
                                    |   Your Email     |
                                    +------------------+
```

## Features

- Automatic file backup on upload
- Email notifications via SNS
- Server-side encryption (SSE-S3)
- Bucket versioning for file history
- Public access blocking for security
- Optional CloudTrail audit logging
- Infrastructure as Code (SAM/CloudFormation)

## AWS Services Used

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| S3 | Source and backup storage | 5GB storage, 20K GET, 2K PUT |
| Lambda | Event processing | 1M requests/month |
| SNS | Email notifications | 1M publishes/month |
| CloudTrail | Audit logging (optional) | 1 trail free |
| IAM | Access control | Always free |
| CloudWatch | Logging and monitoring | 5GB logs/month |

## Project Structure

```
aws-personal-file-backup/
├── README.md
├── template.yaml              # SAM/CloudFormation template
├── src/
│   └── lambda/
│       └── file_backup_handler.py
├── tests/
│   ├── unit/
│   │   └── test_handler.py
│   └── integration/
│       └── test_e2e.py
├── docs/
│   └── IMPLEMENTATION_PLAN.md
└── scripts/
    ├── deploy.sh
    └── test_upload.sh
```

## Prerequisites

- AWS Account (Free Tier eligible)
- AWS CLI configured with credentials
- AWS SAM CLI installed
- Python 3.9+

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sakeeb91/aws-personal-file-backup.git
   cd aws-personal-file-backup
   ```

2. **Deploy the stack**
   ```bash
   sam build
   sam deploy --guided
   ```

3. **Confirm SNS subscription** (check your email)

4. **Test the backup**
   ```bash
   aws s3 cp test-file.txt s3://your-source-bucket/
   ```

## Testing Matrix

| Case | Action | Expected Result |
|------|--------|-----------------|
| Happy path | Upload sample.pdf to source | Object appears in backup, SNS email received |
| Duplicate event | Re-process same key | Lambda logs skip_copy, only one backup exists |
| Large object | Upload 100+ MB | Copy completes (server-side), no timeout |
| Versioned rewrite | Upload same key twice | Backup has latest version; source has versions |
| Permission error | Remove sns:Publish | Lambda copy OK, but log error; no email |
| Encryption | Upload w/o SSE header | Bucket enforces SSE-S3; object encrypted |
| Error visibility | Force typo in env var | Lambda 5xx + CloudWatch error log |
| Audit | With CloudTrail on | New S3 write event visible in trail logs |

## Cost Estimate

For typical personal use (< 5GB storage, < 1000 files/month):

| Service | Monthly Cost |
|---------|--------------|
| S3 Storage | $0.00 (Free Tier) |
| Lambda | $0.00 (Free Tier) |
| SNS | $0.00 (Free Tier) |
| CloudTrail | $0.00 (1 trail free) |
| **Total** | **$0.00** |

## Security Considerations

- All buckets have public access blocked
- Server-side encryption enabled (SSE-S3)
- Lambda uses least-privilege IAM role
- No hardcoded credentials
- CloudTrail provides audit trail

## Future Enhancements

- [ ] Support for multiple backup destinations
- [ ] File type filtering
- [ ] Backup retention policies
- [ ] Cross-region replication
- [ ] Slack/Discord notifications
- [ ] Web dashboard for monitoring

## License

MIT License

## Author

Sakeeb Rahman - [GitHub](https://github.com/Sakeeb91)
