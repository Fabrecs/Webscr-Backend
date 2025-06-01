import boto3
import os
import uuid
from dotenv import load_dotenv
from typing import List
from utils.s3_utils import generate_signed_urls

# Load environment variables
load_dotenv()

class S3Service:
    def __init__(self):
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_REGION")
        self.s3_bucket_name = os.getenv("S3_BUCKET_NAME")
        self.s3_client = self._create_s3_client()

    def _create_s3_client(self):
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.aws_region, self.s3_bucket_name]):
            print("Warning: AWS credentials or S3 bucket name not fully configured. S3 operations will fail.")
            return None
        try:
            return boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region,
                config=boto3.session.Config(signature_version='s3v4')
            )
        except Exception as e:
            print(f"Error creating S3 client: {e}")
            return None
           
    def generate_presigned_urls(self, count: int, content_type: List[str] = None) -> List[str]:
        if self.s3_client is None or self.s3_bucket_name is None:
            raise ValueError("S3 client is not configured due to missing environment variables.")

        if count <= 0:
            raise ValueError("Count must be a positive integer.")

        if count > 10:
            raise ValueError("Cannot request more than 10 URLs at a time.")

        # Generate object keys
        object_keys = []
        content_types = []
        
        for i in range(count):
            object_key = f"Recommendations/{uuid.uuid4()}.jpg"
            object_keys.append(object_key)
            
            # Add content type
            ct = content_type[i] if content_type and i < len(content_type) else "image/jpeg"
            content_types.append(ct)
        
        try:
            # Use utility function for generating presigned URLs
            presigned_urls = generate_signed_urls(
                object_keys=object_keys,
                client_method='put_object',
                expiration=3600,
                content_types=content_types,
                bucket_name=self.s3_bucket_name
            )
            
            # Check if any URL is None (failed to generate)
            if None in presigned_urls:
                raise ConnectionError("Failed to generate one or more signed URLs")
                
            return presigned_urls
        except Exception as e:
            print(f"Error generating presigned PUT URLs: {e}")
            raise ConnectionError("Could not generate signed URLs.")

