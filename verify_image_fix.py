
import os
import sys
from unittest.mock import MagicMock

# Mock app context
from flask import Flask, Config

# sys.path.append('/home/usuario/tandil_ai/SaaS-Stock')

from app.models.product import Product
from app.services.storage_service import StorageService

def test_product_url_generation():
    print("Testing Product URL generation...")
    
    app = Flask(__name__)
    app.config['S3_PUBLIC_URL'] = 'http://localhost:9000'
    app.config['S3_BUCKET'] = 'uploads'
    
    with app.app_context():
        # Case 1: Legacy Full URL
        p1 = Product(image_path='https://minio.tandil.site/uploads/products/old.jpg')
        assert p1.image_url == 'https://minio.tandil.site/uploads/products/old.jpg'
        print("✓ Legacy URL handled correctly")
        
        # Case 2: New Relative Path
        p2 = Product(image_path='products/tenant_1/new.jpg')
        expected = 'http://localhost:9000/uploads/products/tenant_1/new.jpg'
        assert p2.image_url == expected
        print(f"✓ Relative path handled correctly: {p2.image_url}")
        
        # Case 3: No Image
        p3 = Product(image_path=None)
        assert p3.image_url is None
        print("✓ No image handled correctly")

def test_storage_service_upload_return():
    print("\nTesting StorageService upload return value...")
    
    from unittest.mock import patch
    
    with patch('app.services.storage_service.boto3') as mock_boto3:
        app = Flask(__name__)
        app.config['S3_ENDPOINT'] = 'http://minio:9000'
        app.config['S3_ACCESS_KEY'] = 'minio'
        app.config['S3_SECRET_KEY'] = 'minio123'
        app.config['S3_BUCKET'] = 'uploads'
        app.config['S3_REGION'] = 'us-east-1'
        app.config['S3_PUBLIC_URL'] = 'http://localhost:9000'
        app.config['MAX_UPLOAD_SIZE'] = 1024 * 1024
        
        with app.app_context():
            # Mock the client returned by boto3.client
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            
            # Mock head_bucket to avoid logic in __init__
            mock_client.head_bucket.return_value = {}
            
            storage = StorageService()
            
            # Create a mock file
            file_mock = MagicMock()
            file_mock.filename = 'test.jpg'
            file_mock.filename = 'test.jpg'
            file_mock.content_type = 'image/jpeg'
            file_mock.tell.return_value = 1024  # 1KB file size
            
            # Mock upload_fileobj
            mock_client.upload_fileobj.return_value = None
            
            result = storage.upload_file(file_mock, 'products/test.jpg')
            
            # It should return the key, NOT the full URL
            assert result == 'products/test.jpg'
            print(f"✓ storage.upload_file returned key as expected: {result}")

if __name__ == "__main__":
    try:
        test_product_url_generation()
        test_storage_service_upload_return()
        print("\nALL VERIFICATIONS PASSED")
    except AssertionError as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
