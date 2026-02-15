"""
Object Storage Service for S3-compatible storage.
Ensures stateless Flask instances and horizontal scalability.
"""

import logging
import mimetypes
import os
import json
from typing import Optional, Dict, Any
from io import BytesIO

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from flask import Flask, current_app
from werkzeug.datastructures import FileStorage
from app.exceptions import BusinessLogicError

logger = logging.getLogger(__name__)


class StorageService:
    """S3-compatible object storage service."""
    
    def __init__(self, app: Optional[Flask] = None):
        """Initialize storage service."""
        self.endpoint: str = ""
        self.access_key: str = ""
        self.secret_key: str = ""
        self.bucket: str = ""
        self.region: str = ""
        self.public_url: str = ""
        self.client: Any = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """Initialize S3 client from Flask app config."""
        self.endpoint = app.config.get('S3_ENDPOINT', 'http://minio:9000')
        self.access_key = app.config.get('S3_ACCESS_KEY', 'minioadmin')
        self.secret_key = app.config.get('S3_SECRET_KEY', 'minioadmin')
        self.bucket = app.config.get('S3_BUCKET', 'uploads')
        self.region = app.config.get('S3_REGION', 'us-east-1')
        self.public_url = app.config.get('S3_PUBLIC_URL', 'http://localhost:9000')
        
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=BotoConfig(signature_version='s3v4')
        )
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == '404':
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    policy = {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": "s3:GetObject",
                            "Resource": f"arn:aws:s3:::{self.bucket}/*"
                        }]
                    }
                    self.client.put_bucket_policy(Bucket=self.bucket, Policy=json.dumps(policy))
                    logger.info(f"[STORAGE] Bucket '{self.bucket}' created with public-read policy")
                except ClientError as create_error:
                    logger.error(f"[STORAGE] Failed to create bucket: {create_error}")
            else:
                logger.error(f"[STORAGE] Failed to check bucket: {e}")
    
    def upload_file(self, file: FileStorage, object_name: str, content_type: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> str:
        """Upload file to S3 and return object key."""
        self._validate_file(file)
        if not content_type:
            content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or 'application/octet-stream'
        
        extra_args: Dict[str, Any] = {'ContentType': content_type, 'ACL': 'public-read'}
        if metadata: extra_args['Metadata'] = metadata
        
        try:
            file.seek(0)
            self.client.upload_fileobj(file.stream, self.bucket, object_name, ExtraArgs=extra_args)
            return object_name
        except ClientError as e:
            logger.exception(f"[STORAGE] Upload failed: {e}")
            raise
    
    def delete_file(self, object_name: str) -> bool:
        """Delete file from storage."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=object_name)
            return True
        except ClientError as e:
            logger.exception(f"[STORAGE] Delete failed: {e}")
            return False
    
    def get_public_url(self, object_name: str) -> str:
        """Get public URL for an object."""
        return f"{self.public_url}/{self.bucket}/{object_name}"
    
    def file_exists(self, object_name: str) -> bool:
        """Check if file exists."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_name)
            return True
        except ClientError:
            return False
    
    def _validate_file(self, file: FileStorage) -> None:
        """Validate file size and type."""
        if not file or not file.filename:
            raise BusinessLogicError("No se proporcionó ningún archivo")
        
        max_size = current_app.config.get('MAX_UPLOAD_SIZE', 2 * 1024 * 1024)
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        
        if size > max_size:
            raise BusinessLogicError(f"Archivo demasiado grande (máx {max_size/(1024*1024):.1f}MB)")
        
        allowed = current_app.config.get('ALLOWED_MIME_TYPES', set())
        if allowed and file.content_type not in allowed:
            raise BusinessLogicError(f"Tipo no permitido: {file.content_type}")
    
    def upload_tenant_logo(self, file: FileStorage, tenant_id: int) -> str:
        """Upload business logo."""
        allowed_types = {'image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp'}
        if file.content_type not in allowed_types:
            raise BusinessLogicError(f"Formato no permitido: {file.content_type}")
        
        ext = os.path.splitext(file.filename or "")[1]
        object_name = f"logos/{tenant_id}/business_logo{ext}"
        return self.upload_file(file, object_name, file.content_type)
    
    def delete_tenant_logo(self, logo_url: str) -> bool:
        """Delete tenant logo."""
        return self.delete_file(logo_url) if logo_url else False


_storage_service: Optional[StorageService] = None

def get_storage_service() -> StorageService:
    """Get StorageService singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
        # En caso de que se llame fuera del contexto, el init_app se llamará en el factory
    return _storage_service
