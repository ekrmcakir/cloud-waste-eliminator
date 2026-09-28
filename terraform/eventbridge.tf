resource "aws_cloudwatch_event_rule" "nightly_waste_scan" {
  name                = "finops-nightly-cloud-waste-scan"
  description         = "Triggers FinOps Scanner Lambda on a scheduled nightly cron"
  schedule_expression = var.scan_schedule_expression
}

resource "aws_cloudwatch_event_target" "trigger_scanner_lambda" {
  rule      = aws_cloudwatch_event_rule.nightly_waste_scan.name
  target_id = "TriggerFinOpsScanner"
  arn       = aws_lambda_function.scanner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_to_call_scanner" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.nightly_waste_scan.arn
}
