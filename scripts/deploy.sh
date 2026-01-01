#!/bin/bash
# Deploy the Personal File Backup stack to AWS

set -e

echo "Building SAM application..."
sam build

echo "Deploying to AWS..."
sam deploy --guided

echo "Deployment complete!"
echo "Remember to confirm the SNS email subscription."
