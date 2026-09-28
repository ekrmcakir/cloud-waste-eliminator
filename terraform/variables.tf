variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name for FinOps findings and approvals"
  type        = string
  default     = "finops-cloud-waste-findings"
}

variable "scan_schedule_expression" {
  description = "EventBridge cron schedule for automatic waste scanning"
  type        = string
  default     = "cron(0 3 * * ? *)" # Every day at 03:00 UTC
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock model ID for FinOps analysis"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}
