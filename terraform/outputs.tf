output "dynamodb_table_arn" {
  description = "ARN of the FinOps findings DynamoDB table"
  value       = aws_dynamodb_table.waste_findings.arn
}

output "dynamodb_table_name" {
  description = "Name of the FinOps findings DynamoDB table"
  value       = aws_dynamodb_table.waste_findings.name
}

output "scanner_lambda_arn" {
  description = "ARN of the Scanner Lambda function"
  value       = aws_lambda_function.scanner.arn
}

output "remediation_lambda_arn" {
  description = "ARN of the Remediation Lambda function"
  value       = aws_lambda_function.remediation.arn
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge cron rule"
  value       = aws_cloudwatch_event_rule.nightly_waste_scan.arn
}
