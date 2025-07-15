variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "sp_api_client" {
  description = "Selling Partner API Client ID"
  type        = string
  sensitive   = true
}

variable "sp_api_secret" {
  description = "Selling Partner API Client Secret"
  type        = string
  sensitive   = true
}

variable "sp_api_refresh" {
  description = "Selling Partner API Refresh Token"
  type        = string
  sensitive   = true
}