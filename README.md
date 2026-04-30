# Project 32: CloudFront Cache Invalidator Lambda

A Python 3.9 AWS Lambda function that performs targeted CloudFront cache invalidations for user-profile style URLs. The handler accepts a `profileUrl` from any of three input sources, normalises it, and issues a single `CreateInvalidation` call covering three path patterns: the exact URL, its subtree, and its query-string variants. One request purges every cached variant of a changed resource.

## Why It Exists

When a user profile, article, or any cacheable resource is updated, the application needs to flush every cached representation of it from CloudFront edge locations: the canonical URL, sub-pages under it (`/users/42/photos`, `/users/42/posts`), and any cache-busted variants with query strings (`/users/42?v=2`). Doing this in three separate API calls is wasteful. This Lambda batches all three patterns into a single `CreateInvalidation` call.

## How It Works

```
Caller (admin UI, CMS webhook, profile-update API, etc.)
        |
        | { "profileUrl": "/users/42" }
        v
Lambda (Python 3.9, 128 MB, 30s timeout)
   1. Locate profileUrl in event (3 input sources, see below)
   2. Normalise URL (prepend "/" if missing)
   3. Build invalidation patterns:
        /users/42
        /users/42/*      (subtree)
        /users/42?*      (query-string variants)
   4. cloudfront.create_invalidation(DistributionId, Paths, CallerReference=time.time())
        |
        v
CloudFront distribution -> edge caches drop those paths
```

### Input Source Resolution

The handler works as a Lambda Function URL, an API Gateway integration, or a direct SDK invoke. It searches for `profileUrl` in this order:

1. `event.queryStringParameters.profileUrl` — Function URL or API Gateway with parsed query string
2. `event.rawQueryString` — API Gateway HTTP API with raw query string
3. `event.body` — POST request body, parsed as JSON
4. `event.profileUrl` — direct SDK invoke with a flat payload

Whichever source supplies the value first wins. This lets the same Lambda be wired into three different integration patterns without modification.

### Path Pattern Logic

For an input of `/users/42`, the handler builds:

| Pattern | Purpose |
|---|---|
| `/users/42` | The exact resource URL |
| `/users/42/*` | Any sub-pages under the resource (e.g. `/users/42/photos`, `/users/42/posts`) |
| `/users/42?*` | Any cache-busted variants (`/users/42?v=2`, `/users/42?lang=en`) |

CloudFront treats this as 3 paths in 1 invalidation request, which keeps the API call count low. Note that CloudFront's free tier of 1,000 invalidation paths per month counts paths, not requests, so batching saves API overhead but not direct CloudFront cost beyond the free tier.

### Response Shape

Success (HTTP 200):

```json
{
  "message": "Cache invalidation initiated",
  "result": {
    "invalidationId": "I2XAMPLEJ5ABC",
    "status": "InProgress",
    "paths": ["/users/42", "/users/42/*", "/users/42?*"]
  }
}
```

Failure cases:
- `400` — `profileUrl` missing or empty
- `500` — unexpected exception. Error details are written to CloudWatch Logs only, not returned to the caller.

`Content-Type: application/json` is set on every response.

## What Gets Provisioned

The included Terraform module provisions everything in one apply:

- IAM execution role for the Lambda
- IAM policy scoped to `cloudfront:CreateInvalidation` and `cloudfront:GetInvalidation` against a single distribution ARN (not `*`)
- CloudWatch Logs permissions
- Lambda function (Python 3.9, 128 MB, 30 second timeout)

Outputs `lambda_arn` and `lambda_function_name` are exported for downstream wiring.

## Stack

Python 3.9 · boto3 · Terraform · AWS Lambda · CloudFront · IAM · CloudWatch Logs

## Prerequisites

- Terraform >= 1.x
- AWS credentials with permissions to create IAM roles, Lambda functions, and reference an existing CloudFront distribution
- A CloudFront distribution ID. Replace `<distribution-id>` in both `invalidate_cache.py` (`CLOUDFRONT_ID`) and `main.tf` (IAM resource ARN), or parameterise as a Terraform variable

## Deployment

```bash
zip invalidate_cache.zip invalidate_cache.py

terraform init
terraform plan
terraform apply
```

To expose the Lambda over HTTP, either add a Lambda Function URL via `aws lambda create-function-url-config`, or place it behind an API Gateway.

## Example Invocations

Direct SDK invoke:

```bash
aws lambda invoke --function-name cloudfront_cache_invalidator \
  --payload '{"profileUrl": "/users/42"}' out.json
```

Function URL (HTTP GET):

```bash
curl "https://<fn-url>/?profileUrl=/users/42"
```

## Teardown

```bash
terraform destroy
```

## Notes

- The CloudFront distribution ID is hardcoded in both `invalidate_cache.py` and the IAM policy in `main.tf`. Parameterise both as Terraform variables before reusing across accounts or distributions.
- `CallerReference` uses `time.time()`. Two invalidations issued within the same second could be deduplicated by CloudFront. Switch to `uuid.uuid4()` for fully idempotent retry semantics.
- The Lambda has no authentication if exposed via Function URL. Add IAM auth or place it behind API Gateway with an authorizer before exposing externally.
- Error responses to clients are intentionally minimal (`{"error": "..."}`). Full exception traces stay in CloudWatch Logs, not in API responses.
- CloudFront's free tier is 1,000 invalidation paths per month. Beyond that, each path is billed at the published rate. Batching three patterns in one call saves API request overhead, not per-path cost.
