"""
Object Storage Service for S3-compatible storage (MinIO, AWS S3, DigitalOcean Spaces).

This service provides a unified interface for file uploads, ensuring
stateless Flask instances and horizontal scalability.

Architecture:
- Uses boto3 (AWS SDK for Python)
- Compatible with MinIO (local), AWS S3, DigitalOcean Spaces
- Supports public-read and private objects
- Automatic bucket creation on init
"""
import logging
import mimetypes
from typing import Optional
from io import BytesIO

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from flask import current_app
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


class StorageService:
    """
    S3-compatible object storage service.
    
    Usage:
        storage = StorageService()
        url = storage.upload_file(file, 'products/image.jpg', 'image/jpeg')
        storage.delete_file('products/image.jpg')
    """
    
    def __init__(self):
        """Initialize S3 client from Flask config."""
        self.endpoint = current_app.config['S3_ENDPOINT']
        self.access_key = current_app.config['S3_ACCESS_KEY']
        self.secret_key = current_app.config['S3_SECRET_KEY']
        self.bucket = current_app.config['S3_BUCKET']
        self.region = current_app.config['S3_REGION']
        self.public_url = current_app.config['S3_PUBLIC_URL']
        
        # Initialize boto3 S3 client
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=BotoConfig(signature_version='s3v4')
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
            logger.info(f"[STORAGE] Bucket '{self.bucket}' exists")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    logger.info(f"[STORAGE] ✓ Bucket '{self.bucket}' created")
                    
                    # Set bucket policy for public read (for product images)
                    policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": "*"},
                                "Action": "s3:GetObject",
                                "Resource": f"arn:aws:s3:::{self.bucket}/*"
                            }
                        ]
                    }
                    import json
                    self.client.put_bucket_policy(
                        Bucket=self.bucket,
                        Policy=json.dumps(policy)
                    )
                    logger.info(f"[STORAGE] ✓ Bucket '{self.bucket}' policy set to public-read")
                except ClientError as create_error:
                    logger.error(f"[STORAGE] ✗ Failed to create bucket: {create_error}")
                    raise
            else:
                logger.error(f"[STORAGE] ✗ Failed to check bucket: {e}")
                raise
    
    def upload_file(
        self,
        file: FileStorage,
        object_name: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload file to S3-compatible storage.
        
        Args:
            file: Werkzeug FileStorage object from request.files
            object_name: S3 object key (path in bucket, e.g., 'products/123_image.jpg')
            content_type: MIME type (auto-detected if None)
            metadata: Optional metadata dict
        
        Returns:
            Public URL of uploaded file
        
        Raises:
            ValueError: If file validation fails
            ClientError: If upload fails
        """
        # Validate file
        self._validate_file(file)
        
        # Auto-detect content type
        if not content_type:
            content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
        
        # Prepare extra args
        extra_args = {
            'ContentType': content_type,
            'ACL': 'public-read'  # Make file publicly accessible
        }
        
        if metadata:
            extra_args['Metadata'] = metadata
        
        try:
            # Reset file pointer
            file.seek(0)
            
            # Upload to S3
            logger.info(f"[STORAGE] Uploading '{object_name}' to bucket '{self.bucket}'...")
            self.client.upload_fileobj(
                file.stream,
                self.bucket,
                object_name,
                ExtraArgs=extra_args
            )
            
            # Generate public URL
            url = self.get_public_url(object_name)
            logger.info(f"[STORAGE] ✓ File uploaded: {url}")
            return url
            
        except ClientError as e:
            logger.exception(f"[STORAGE] ✗ Upload failed: {e}")
            raise
    
    def delete_file(self, object_name: str) -> bool:
        """
        Delete file from S3-compatible storage.
        
        Args:
            object_name: S3 object key (e.g., 'products/123_image.jpg')
        
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            logger.info(f"[STORAGE] Deleting '{object_name}' from bucket '{self.bucket}'...")
            self.client.delete_object(Bucket=self.bucket, Key=object_name)
            logger.info(f"[STORAGE] ✓ File deleted: {object_name}")
            return True
        except ClientError as e:
            logger.exception(f"[STORAGE] ✗ Delete failed: {e}")
            return False
    
    def get_public_url(self, object_name: str) -> str:
        """
        Get public URL for an object.
        
        Args:
            object_name: S3 object key
        
        Returns:
            Public URL (e.g., 'http://localhost:9000/uploads/products/image.jpg')
        """
        return f"{self.public_url}/{self.bucket}/{object_name}"
    
    def file_exists(self, object_name: str) -> bool:
        """
        Check if file exists in S3.
        
        Args:
            object_name: S3 object key
        
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_name)
            return True
        except ClientError:
            return False
    
    def _validate_file(self, file: FileStorage):
        """
        Validate uploaded file (size, type, etc.).
        
        Args:
            file: Werkzeug FileStorage object
        
        Raises:
            ValueError: If validation fails
        """
        if not file or not file.filename:
            raise ValueError("No se proporcionó ningún archivo")
        
        # Check file size
        max_size = current_app.config.get('MAX_UPLOAD_SIZE', 2 * 1024 * 1024)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset
        
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise ValueError(f"El archivo es demasiado grande. Máximo {max_mb:.1f}MB")
        
        # Check MIME type
        allowed_types = current_app.config.get('ALLOWED_MIME_TYPES', set())
        content_type = file.content_type
        
        if allowed_types and content_type not in allowed_types:
            raise ValueError(f"Tipo de archivo no permitido: {content_type}. Permitidos: {', '.join(allowed_types)}")
        
        logger.info(f"[STORAGE] ✓ File validation passed: {file.filename} ({file_size} bytes, {content_type})")


# Singleton instance
_storage_service = None


def get_storage_service() -> StorageService:
    """
    Get or create StorageService singleton.
    
    Returns:
        StorageService instance
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
