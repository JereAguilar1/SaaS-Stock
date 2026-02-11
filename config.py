"""Configuration module for Flask application."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class."""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'
    ENV = os.getenv('FLASK_ENV', 'development')
    
    # Session Configuration (Production-safe defaults)
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Preferred URL scheme (for url_for with _external=True)
    PREFERRED_URL_SCHEME = os.getenv('PREFERRED_URL_SCHEME', 'http')
    
    # Authentication (MEJORA 8 - Password Protection)
    APP_PASSWORD = os.getenv('APP_PASSWORD')
    SESSION_AUTH_KEY = os.getenv('SESSION_AUTH_KEY', 'authenticated')
    
    # Database - Support multiple environment variable naming conventions
    # Priority: DATABASE_URL > DB_* > POSTGRES_*
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        # Try DB_* variables (Docker style)
        DB_HOST = os.getenv('DB_HOST') or os.getenv('POSTGRES_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT') or os.getenv('POSTGRES_PORT', '5432')
        DB_NAME = os.getenv('DB_NAME') or os.getenv('POSTGRES_DB', 'stock')
        DB_USER = os.getenv('DB_USER') or os.getenv('POSTGRES_USER', 'stock')
        DB_PASSWORD = os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD', 'stock')
        
        DATABASE_URL = (
            f"postgresql://{DB_USER}:{DB_PASSWORD}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    
    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = DEBUG
    
    # Stock Configuration (MEJORA 10 - Stock Filters)
    LOW_STOCK_THRESHOLD = int(os.getenv('LOW_STOCK_THRESHOLD', '10'))
    
    # Business Information (for quotes/invoices)
    BUSINESS_NAME = os.getenv('BUSINESS_NAME', 'Mi Negocio')
    BUSINESS_ADDRESS = os.getenv('BUSINESS_ADDRESS', '')
    BUSINESS_PHONE = os.getenv('BUSINESS_PHONE', '')
    BUSINESS_EMAIL = os.getenv('BUSINESS_EMAIL', '')
    QUOTE_VALID_DAYS = int(os.getenv('QUOTE_VALID_DAYS', '7'))
    
    # Email configuration (PASO 6)
    MAIL_SERVER = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('SMTP_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.getenv('SMTP_USER') or ''
    MAIL_PASSWORD = os.getenv('SMTP_PASSWORD') or ''
    MAIL_DEFAULT_SENDER = (
        os.getenv('SMTP_FROM')
        or MAIL_USERNAME
        or 'no-reply@localhost'
    )
    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = False
    
    # Object Storage Configuration (PASO 7 - MinIO/S3)
    # Compatible with AWS S3, DigitalOcean Spaces, MinIO
    S3_ENDPOINT = os.getenv('S3_ENDPOINT', 'http://minio:9000')
    S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', 'minioadmin')
    S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', 'minioadmin')
    S3_BUCKET = os.getenv('S3_BUCKET', 'uploads')
    S3_REGION = os.getenv('S3_REGION', 'us-east-1')
    S3_PUBLIC_URL = os.getenv('S3_PUBLIC_URL', 'http://localhost:9000')
    
    # Upload constraints
    MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', 2 * 1024 * 1024))  # 2MB
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    ALLOWED_MIME_TYPES = {
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp'
    }
    
    # Redis Cache Configuration (PASO 8)
    # Shared cache layer for reducing PostgreSQL load and accelerating read endpoints
    REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
    CACHE_DEFAULT_TTL = int(os.getenv('CACHE_DEFAULT_TTL', '60'))  # seconds
    CACHE_PRODUCTS_TTL = int(os.getenv('CACHE_PRODUCTS_TTL', '60'))
    CACHE_CATEGORIES_TTL = int(os.getenv('CACHE_CATEGORIES_TTL', '300'))
    CACHE_UOM_TTL = int(os.getenv('CACHE_UOM_TTL', '3600'))
    CACHE_BALANCE_TTL = int(os.getenv('CACHE_BALANCE_TTL', '60'))
    CACHE_NEGATIVE_TTL = int(os.getenv('CACHE_NEGATIVE_TTL', '15'))  # For "cache miss"
    CACHE_KEY_PREFIX = os.getenv('CACHE_KEY_PREFIX', 'stock')


