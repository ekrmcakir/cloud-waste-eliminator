data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/lambda_payload.zip"
}

resource "aws_lambda_function" "scanner" {
  function_name    = "finops-waste-scanner"
  role             = aws_iam_role.scanner_role.arn
  handler          = "handlers.scan_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 256
  filename         = data.archive_file.lambda_package.output_path
  source_code_hash = data.archive_file.lambda_package.output_base64sha256

  environment {
    variables = {
      FINOPS_TABLE_NAME = aws_dynamodb_table.waste_findings.name
      BEDROCK_MODEL_ID  = var.bedrock_model_id
      ENABLE_AI_ADVISOR = "true"
      FINOPS_DRY_RUN    = "false"
    }
  }

  tags = {
    Environment = var.environment
    Service     = "FinOps"
  }
}

resource "aws_lambda_function" "remediation" {
  function_name    = "finops-waste-remediator"
  role             = aws_iam_role.remediation_role.arn
  handler          = "handlers.remediation_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 180
  memory_size      = 256
  filename         = data.archive_file.lambda_package.output_path
  source_code_hash = data.archive_file.lambda_package.output_base64sha256

  environment {
    variables = {
      FINOPS_TABLE_NAME = aws_dynamodb_table.waste_findings.name
      FINOPS_DRY_RUN    = "false"
    }
  }

  tags = {
    Environment = var.environment
    Service     = "FinOps"
  }
}
