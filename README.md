# CloudFront Cache Invalidator Lambda

Python 3.9 Lambda function that performs on-demand CloudFront cache invalidations for user-profile style URLs, scoped to a single distribution. Accepts a `profileUrl` from three sources (query string, raw query string, or JSON body), normalises it, then issues a `CreateInvalidation` call against three path patterns — the exact URL, its subtree, and its query-string variants — so a single request purges every cached variant of a changed profile.

## Highlights

- **Three path patterns in one call** — for input `/users/42`, issues an invalidation for `/users/42`, `/users/42/*`, `/users/42?*`. Covers sub-pages and cache-busted variants in a single CloudFront call (one billable invalidation).
- **Triple input handling** — works as a Function URL (`queryStringParameters`), as an API Gateway REST/HTTP integration (`rawQueryString`), and as a direct SDK invoke (`event.profileUrl`). One handler, three integration options.
- **Least-privilege IAM** — the Terraform module scopes `cloudfront:CreateInvalidation` / `GetInvalidation` to a single distribution ARN, not `*`.
- **Structured JSON responses** — returns `{ message, result: { invalidationId, status, paths } }` on success, `{ error }` with the right HTTP status on failure; `Content-Type: application/json` always set.
- **Batteries-included Terraform** — IAM role, IAM policy, CloudWatch Logs attachment, and Lambda function all defined in one file with exportable `lambda_arn` / `lambda_function_name` outputs.

## Architecture

```
 Any upstream service (admin UI, CMS webhook, profile-update API)
              │
              │  { "profileUrl": "/users/42" }
              ▼
 Lambda (Python 3.9, 128 MB, 30 s timeout)
   ├─ normalise URL (prepend "/" if missing)
   ├─ build patterns [url, url/*, url?*]
   └─ cloudfront.create_invalidation(DistributionId=E3FUR8VHNU616N, Paths=...)
              │
              ▼
 CloudFront distribution  →  edge caches drop those paths
```

## Tech stack

- **Runtime:** Python 3.9
- **Libraries:** `boto3` (built into the Lambda runtime)
- **Infrastructure:** Terraform
- **AWS services:** Lambda, CloudFront (CreateInvalidation), IAM, CloudWatch Logs

## Repository layout

```
LAMBDA-CLOUDFRONT-CACHE/
├── README.md
├── .gitignore
├── invalidate_cache.py   # Lambda handler
└── main.tf               # IAM + Lambda + logging
```

## How it works

1. Caller invokes the Lambda (Function URL, API Gateway, or direct SDK) with a `profileUrl`.
2. Handler locates `profileUrl` in `event.queryStringParameters`, then `event.rawQueryString`, then `event.body` (parsed as JSON), then the top-level `event` — whichever is present.
3. Normalises the URL to ensure it starts with `/`.
4. Builds three invalidation patterns and calls `cloudfront.create_invalidation` with a `CallerReference` derived from `time.time()` (so retries aren't deduplicated by CloudFront).
5. Returns `200` with the invalidation ID, status, and paths on success; `400` if `profileUrl` is missing; `500` for unexpected exceptions (details in CloudWatch Logs only).

## Prerequisites

- Terraform >= 1.x
- Python 3.9
- AWS CLI configured with permissions to create IAM roles, Lambda functions, and manage CloudFront
- A real CloudFront distribution ID — replace `E3FUR8VHNU616N` in both `invalidate_cache.py` (`CLOUDFRONT_ID`) and `main.tf` (IAM resource ARN)

## Deployment

```bash
# Package the function
zip invalidate_cache.zip invalidate_cache.py

# Apply infrastructure
terraform init
terraform plan
terraform apply
```

To expose it as an HTTP endpoint, either add a Lambda Function URL (`aws lambda create-function-url-config`) or wire it behind API Gateway.

## Example invocation

```bash
# Direct Lambda invoke
aws lambda invoke --function-name cloudfront_cache_invalidator \
  --payload '{"profileUrl": "/users/42"}' out.json

# HTTP (Function URL)
curl "https://<fn-url>/?profileUrl=/users/42"
```

Response:
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

## Teardown

```bash
terraform destroy
```

## Notes

- CloudFront currently charges for invalidations beyond 1,000 paths/month — batching the three patterns in a single call counts as 3 paths, not 3 invalidations, which is cheaper.
- The hardcoded distribution ID should be parameterised via a Terraform `variable` before re-use in another account.
- Demonstrates: CloudFront operational automation, multi-source event parsing in a single Lambda handler, scoped IAM, Terraform-packaged serverless unit.
