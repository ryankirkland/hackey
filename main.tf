#------------------------------------------------------------
# Provider & Data Sources
#------------------------------------------------------------
provider "aws" {
  region = var.aws_region
  profile = var.aws_profile
}

data "aws_caller_identity" "current" {}

#------------------------------------------------------------
# Generate a random suffix for unique bucket names
#------------------------------------------------------------
resource "random_id" "bucket_suffix" {
  byte_length = 8
}

#------------------------------------------------------------
# S3 buckets for Lambda code and for report data
#------------------------------------------------------------
resource "aws_s3_bucket" "lambda_code" {
  bucket = "sp-reports-lambda-code-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "lambda_code_versioning" {
  bucket = aws_s3_bucket.lambda_code.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lambda_code_encryption" {
  bucket = aws_s3_bucket.lambda_code.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket" "reports_data" {
  bucket = "sp-reports-data-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "reports_data_versioning" {
  bucket = aws_s3_bucket.reports_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports_data_encryption" {
  bucket = aws_s3_bucket.reports_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

#------------------------------------------------------------
# Package & Upload Lambda Function Code
#------------------------------------------------------------
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "reports.py"
  output_path = "reports.zip"
}

resource "aws_s3_object" "lambda_zip" {
  bucket = aws_s3_bucket.lambda_code.id
  key    = "reports.zip"
  source = data.archive_file.lambda_zip.output_path
  etag   = data.archive_file.lambda_zip.output_md5
}

#------------------------------------------------------------
# IAM Role & Policy for Lambda
#------------------------------------------------------------
resource "aws_iam_role" "lambda_role" {
  name = "sp-reports-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name   = "sp-reports-lambda-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.reports_data.arn}/*",
          "${aws_s3_bucket.lambda_code.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [
          aws_s3_bucket.reports_data.arn,
          aws_s3_bucket.lambda_code.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

#------------------------------------------------------------
# Fetch SP-API Credentials from Secrets Manager
#------------------------------------------------------------
data "aws_secretsmanager_secret_version" "sp_api_credentials" {
  secret_id = "sp_api/epic_hackey"
}

locals {
  sp_creds = jsondecode(data.aws_secretsmanager_secret_version.sp_api_credentials.secret_string)
}

#------------------------------------------------------------
# Lambda Function
#------------------------------------------------------------
resource "aws_lambda_function" "reports_function" {
  function_name = "sp-reports-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "reports.lambda_handler"
  runtime       = "python3.9"
  timeout       = 900

  s3_bucket = aws_s3_bucket.lambda_code.id
  s3_key    = aws_s3_object.lambda_zip.key

  environment {
    variables = {
      REPORTS_BUCKET = aws_s3_bucket.reports_data.id
      SP_API_CLIENT  = local.sp_creds.SP_API_CLIENT
      SP_API_SECRET  = local.sp_creds.SP_API_SECRET
      SP_API_REFRESH = local.sp_creds.SP_API_REFRESH
    }
  }

  depends_on = [aws_s3_object.lambda_zip]
}

#------------------------------------------------------------
# CloudWatch Event: Daily at 1 AM PST (09:00 UTC)
#------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "daily_reports" {
  name                = "sp-reports-daily"
  description         = "Trigger Lambda function daily at 1am PST"
  schedule_expression = "cron(0 9 * * ? *)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_reports.name
  target_id = "ReportsLambdaTarget"
  arn       = aws_lambda_function.reports_function.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reports_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_reports.arn
}
