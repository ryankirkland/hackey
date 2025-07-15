output "lambda_function_name" {
  value = aws_lambda_function.reports_function.function_name
}

output "reports_bucket_name" {
  value = aws_s3_bucket.reports_data.id
}

output "lambda_code_bucket_name" {
  value = aws_s3_bucket.lambda_code.id
}