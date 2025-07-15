# SP Reports Infrastructure

Terraform configuration for deploying AWS infrastructure to run Amazon Selling Partner API report extraction.

## Architecture

- **S3 Buckets**: 
  - Lambda function code storage
  - Raw sales and traffic report data storage
- **Lambda Function**: Executes reports.py daily at 1am PST
- **CloudWatch Events**: Triggers Lambda on schedule
- **IAM Roles**: Secure permissions for Lambda execution

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform installed (>= 1.0)
- Python dependencies in requirements.txt

## Deployment

1. Copy the example variables file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Edit `terraform.tfvars` with your actual values:
   - AWS region
   - Selling Partner API credentials

3. Initialize and deploy:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

## Environment Variables

The Lambda function uses these environment variables:
- `REPORTS_BUCKET`: S3 bucket for storing report data (set automatically)
- `SP_API_CLIENT`: Selling Partner API Client ID
- `SP_API_SECRET`: Selling Partner API Client Secret  
- `SP_API_REFRESH`: Selling Partner API Refresh Token

## Schedule

The Lambda function runs daily at 1am PST (9am UTC) via CloudWatch Events rule.