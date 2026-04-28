# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "cloudfront_cache_invalidator_role2"

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

# CloudFront invalidation policy
resource "aws_iam_role_policy" "cloudfront_policy" {
  name = "cloudfront_invalidation_policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation",
          "cloudfront:GetInvalidation"
        ]
        Resource = [
          "arn:aws:cloudfront::*:distribution/E3FUR8VHNU616N"
        ]
      }
    ]
  })
}

# CloudWatch Logs policy
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda function
resource "aws_lambda_function" "cache_invalidator" {
  filename         = "invalidate_cache.zip"
  function_name    = "cloudfront_cache_invalidator"
  role            = aws_iam_role.lambda_role.arn
  handler         = "invalidate_cache.lambda_handler"
  runtime         = "python3.9"
  timeout         = 30
  memory_size     = 128

  tags = {
    Name = "cloudfront-cache-invalidator"
  }
}
