# Scanner IAM Role & Policies
resource "aws_iam_role" "scanner_role" {
  name = "finops-scanner-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "scanner_policy" {
  name = "finops-scanner-least-privilege-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeVolumes",
          "ec2:DescribeAddresses",
          "rds:DescribeDBInstances",
          "cloudwatch:GetMetricStatistics",
          "lambda:ListFunctions",
          "lambda:ListTags"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.waste_findings.arn
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "scanner_attach" {
  role       = aws_iam_role.scanner_role.name
  policy_arn = aws_iam_policy.scanner_policy.arn
}

resource "aws_iam_role_policy_attachment" "scanner_basic_logs" {
  role       = aws_iam_role.scanner_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Remediation IAM Role & Policies
resource "aws_iam_role" "remediation_role" {
  name = "finops-remediation-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "remediation_policy" {
  name = "finops-remediation-least-privilege-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateSnapshot",
          "ec2:CreateTags",
          "ec2:DeleteVolume",
          "ec2:ReleaseAddress"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "rds:StopDBInstance"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionConfiguration"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.waste_findings.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "remediation_attach" {
  role       = aws_iam_role.remediation_role.name
  policy_arn = aws_iam_policy.remediation_policy.arn
}

resource "aws_iam_role_policy_attachment" "remediation_basic_logs" {
  role       = aws_iam_role.remediation_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
