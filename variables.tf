variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "aws_profile" {
  description = "AWS profile for all resources."

  type    = string
  default = "ryan"
}