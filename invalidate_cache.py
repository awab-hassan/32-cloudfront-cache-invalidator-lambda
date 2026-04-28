import json
import boto3
import time
import logging
from urllib.parse import parse_qs

logger = logging.getLogger()
logger.setLevel(logging.INFO)
CLOUDFRONT_ID = 'XXXXXXXXXXXXX'  # Replace with your CloudFront distribution ID

def create_invalidation(path_patterns):
    cloudfront = boto3.client('cloudfront')
    
    try:
        response = cloudfront.create_invalidation(
            DistributionId=CLOUDFRONT_ID,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(path_patterns),
                    'Items': path_patterns
                },
                'CallerReference': str(time.time())
            }
        )
        return {
            'invalidationId': response['Invalidation']['Id'],
            'status': response['Invalidation']['Status'],
            'paths': path_patterns
        }
    except Exception as e:
        logger.error(f"Error creating invalidation: {str(e)}")
        raise e

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Handle query parameters from Function URL
        if 'queryStringParameters' in event:
            # Function URL or API Gateway query parameters
            query_params = event.get('queryStringParameters', {}) or {}
            profile_url = query_params.get('profileUrl')
        elif 'rawQueryString' in event:
            # Parse raw query string if present
            raw_params = parse_qs(event['rawQueryString'])
            profile_url = raw_params.get('profileUrl', [None])[0]
        else:
            # Try body for POST requests
            body = event.get('body', '')
            if body:
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError:
                        pass
                profile_url = body.get('profileUrl') if isinstance(body, dict) else None
            else:
                # Direct invocation
                profile_url = event.get('profileUrl')

        if not profile_url:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'profileUrl is required'})
            }
        
        # Ensure the profile URL starts with /
        if not profile_url.startswith('/'):
            profile_url = '/' + profile_url
        
        # Create the invalidation patterns
        patterns = [
            profile_url,           # Exact URL
            f"{profile_url}/*",    # All sub-paths
            f"{profile_url}?*"     # With query parameters
        ]
        
        result = create_invalidation(patterns)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Cache invalidation initiated',
                'result': result
            })
        }
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }