output "lambda_arn" {
  value       = aws_lambda_function.cache_invalidator.arn
  description = "The ARN of the Lambda function"
}

output "lambda_function_name" {
  value       = aws_lambda_function.cache_invalidator.function_name
  description = "The name of the Lambda function"
}

