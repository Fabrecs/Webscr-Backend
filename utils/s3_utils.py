import boto3
import os
from typing import List, Literal, Optional, Dict
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up S3 client
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION")
s3_bucket_name = os.getenv("S3_BUCKET_NAME")

s3_client = None
if all([aws_access_key_id, aws_secret_access_key, aws_region]):
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
            config=boto3.session.Config(signature_version='s3v4')
        )
    except Exception as e:
        print(f"Error creating S3 client: {e}")

def extract_s3_object_key(url: str) -> Optional[Dict[str, str]]:
    """
    Extract bucket name and object key from an S3 URL.
    Returns None if the URL doesn't appear to be an S3 URL.
    """
    try:
        parsed_url = urlparse(url)
        
        # Not an S3/AWS URL
        if not parsed_url.netloc.endswith('.amazonaws.com'):
            return None
            
        path = parsed_url.path.lstrip('/')
        bucket_name = None
        object_key = None
        
        # Format: <bucket>.s3.amazonaws.com/<key>
        host_parts = parsed_url.netloc.split('.')
        if len(host_parts) > 2 and host_parts[1] == 's3':
            bucket_name = host_parts[0]
            object_key = path
        # Format: s3.<region>.amazonaws.com/<bucket>/<key>
        elif host_parts[0] == 's3':
            path_parts = path.split('/', 1)
            if len(path_parts) > 1:
                bucket_name = path_parts[0]
                object_key = path_parts[1]
        
        if bucket_name and object_key:
            return {
                "bucket": bucket_name,
                "key": object_key
            }
        return None
    except Exception as e:
        print(f"Error parsing S3 URL: {e}")
        return None

def generate_signed_urls(
    urls: List[str] = None, 
    object_keys: List[str] = None,
    client_method: Literal['get_object', 'put_object'] = 'get_object',
    expiration: int = 3600,
    content_types: List[str] = None,
    bucket_name: str = None
) -> List[str]:
    """
    Generate presigned S3 URLs for either GET or PUT operations.
    
    Args:
        urls: List of S3 URLs to generate presigned URLs for. Used if object_keys not provided.
        object_keys: List of S3 object keys. Used if provided instead of urls.
        client_method: 'get_object' or 'put_object'
        expiration: URL expiration time in seconds
        content_types: List of content types (required for PUT URLs)
        bucket_name: Override the default bucket name
        
    Returns:
        List of presigned URLs
    """
    if not s3_client:
        raise ValueError("S3 client is not configured due to missing environment variables")
    
    if not bucket_name:
        bucket_name = s3_bucket_name
        
    if not bucket_name:
        raise ValueError("S3 bucket name not provided or found in environment variables")
        
    result_urls = []
    
    # If object_keys provided, use them directly
    if object_keys:
        for i, key in enumerate(object_keys):
            params = {
                'Bucket': bucket_name,
                'Key': key
            }
            
            # Add content type for PUT requests
            if client_method == 'put_object' and content_types and i < len(content_types):
                params['ContentType'] = content_types[i]
                
            try:
                url = s3_client.generate_presigned_url(
                    ClientMethod=client_method,
                    Params=params,
                    ExpiresIn=expiration,
                    HttpMethod='PUT' if client_method == 'put_object' else 'GET'
                )
                result_urls.append(url)
            except Exception as e:
                print(f"Error generating presigned URL for key {key}: {e}")
                result_urls.append(None)
                
    # If URLs provided, extract object keys and generate presigned URLs
    elif urls:
        for i, url in enumerate(urls):
            s3_info = extract_s3_object_key(url)
            if not s3_info:
                result_urls.append(url)  # Return original URL if not an S3 URL
                continue
                
            params = {
                'Bucket': s3_info["bucket"] or bucket_name,
                'Key': s3_info["key"]
            }
            
            # Add content type for PUT requests
            if client_method == 'put_object' and content_types and i < len(content_types):
                params['ContentType'] = content_types[i]
                
            try:
                url = s3_client.generate_presigned_url(
                    ClientMethod=client_method,
                    Params=params,
                    ExpiresIn=expiration,
                    HttpMethod='PUT' if client_method == 'put_object' else 'GET'
                )
                result_urls.append(url)
            except Exception as e:
                print(f"Error generating presigned URL: {e}")
                result_urls.append(None)
    else:
        raise ValueError("Either 'urls' or 'object_keys' must be provided")
        
    return result_urls 