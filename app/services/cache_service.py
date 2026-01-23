"""
Redis Cache Service for Multi-Tenant Application (PASO 8).

This module provides a centralized caching layer with:
- Tenant-isolated cache keys
- Automatic fallback if Redis is unavailable
- Pattern-based invalidation
- TTL management
- JSON serialization with date support

Architecture:
- Uses redis-py with connection pooling
- All keys include tenant_id to prevent data leaks
- Graceful degradation: app continues without cache if Redis is down
"""
import logging
import json
from typing import Any, Optional, Callable
from datetime import datetime, date
from decimal import Decimal

import redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError
from flask import current_app

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service with multi-tenant support.
    
    All cache keys follow the pattern:
        {prefix}:tenant:{tenant_id}:{module}:{key}
    
    Example:
        stock:tenant:1:products:list:page=1&q=martillo
    """
    
    def __init__(self, app=None):
        """Initialize cache service."""
        self.client: Optional[redis.Redis] = None
        self._enabled = False
        self._prefix = ""
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """
        Initialize Redis client from Flask app config.
        
        Args:
            app: Flask application instance
        """
        self._enabled = app.config.get('CACHE_ENABLED', True)
        self._prefix = app.config.get('CACHE_KEY_PREFIX', 'stock')
        redis_url = app.config.get('REDIS_URL', 'redis://redis:6379/0')
        
        if not self._enabled:
            logger.info("[CACHE] Cache is DISABLED via config")
            return
        
        try:
            # Create Redis client with connection pooling and timeouts
            self.client = redis.from_url(
                redis_url,
                decode_responses=True,  # Auto-decode to strings
                socket_connect_timeout=3,
                socket_timeout=3,
                socket_keepalive=True,
                max_connections=50,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.client.ping()
            logger.info(f"[CACHE] ✓ Redis connected: {redis_url}")
            
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"[CACHE] ⚠ Redis connection failed: {e}")
            logger.warning("[CACHE] ⚠ Cache will be DISABLED (app continues without cache)")
            self._enabled = False
            self.client = None
    
    def is_available(self) -> bool:
        """
        Check if cache is available and healthy.
        
        Returns:
            True if Redis is connected and healthy, False otherwise
        """
        if not self._enabled or not self.client:
            return False
        
        try:
            self.client.ping()
            return True
        except (ConnectionError, RedisError):
            return False
    
    def _build_key(self, tenant_id: int, module: str, key: str) -> str:
        """
        Build tenant-isolated cache key.
        
        Args:
            tenant_id: Tenant ID (REQUIRED for multi-tenant isolation)
            module: Module name (e.g., 'products', 'categories', 'balance')
            key: Specific key (e.g., 'list:page=1', 'item:123')
        
        Returns:
            Full cache key with tenant isolation
        
        Example:
            _build_key(1, 'products', 'list:page=1')
            → 'stock:tenant:1:products:list:page=1'
        """
        return f"{self._prefix}:tenant:{tenant_id}:{module}:{key}"
    
    def _serialize(self, value: Any) -> str:
        """
        Serialize Python object to JSON string.
        
        Handles:
        - datetime → ISO format
        - date → ISO format
        - Decimal → float
        - dict, list → JSON
        
        Args:
            value: Python object to serialize
        
        Returns:
            JSON string
        """
        def default_handler(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        return json.dumps(value, default=default_handler)
    
    def _deserialize(self, value: str) -> Any:
        """
        Deserialize JSON string to Python object.
        
        Args:
            value: JSON string
        
        Returns:
            Python object (dict, list, etc.)
        """
        return json.loads(value)
    
    def get(self, tenant_id: int, module: str, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            tenant_id: Tenant ID
            module: Module name
            key: Cache key
        
        Returns:
            Cached value (deserialized) or None if not found or error
        """
        if not self.is_available():
            return None
        
        try:
            cache_key = self._build_key(tenant_id, module, key)
            value = self.client.get(cache_key)
            
            if value is None:
                logger.debug(f"[CACHE] MISS: {cache_key}")
                return None
            
            logger.debug(f"[CACHE] HIT: {cache_key}")
            return self._deserialize(value)
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"[CACHE] ✗ Get error: {e}")
            return None
    
    def set(self, tenant_id: int, module: str, key: str, value: Any, ttl: int = None) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            tenant_id: Tenant ID
            module: Module name
            key: Cache key
            value: Value to cache (will be JSON-serialized)
            ttl: Time to live in seconds (uses default if None)
        
        Returns:
            True if set successfully, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            cache_key = self._build_key(tenant_id, module, key)
            serialized = self._serialize(value)
            
            if ttl is None:
                ttl = current_app.config.get('CACHE_DEFAULT_TTL', 60)
            
            self.client.setex(cache_key, ttl, serialized)
            logger.debug(f"[CACHE] SET: {cache_key} (TTL={ttl}s)")
            return True
            
        except (RedisError, TypeError) as e:
            logger.warning(f"[CACHE] ✗ Set error: {e}")
            return False
    
    def delete(self, tenant_id: int, module: str, key: str) -> bool:
        """
        Delete specific key from cache.
        
        Args:
            tenant_id: Tenant ID
            module: Module name
            key: Cache key
        
        Returns:
            True if deleted, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            cache_key = self._build_key(tenant_id, module, key)
            self.client.delete(cache_key)
            logger.debug(f"[CACHE] DELETE: {cache_key}")
            return True
            
        except RedisError as e:
            logger.warning(f"[CACHE] ✗ Delete error: {e}")
            return False
    
    def delete_pattern(self, tenant_id: int, module: str, pattern: str = "*") -> int:
        """
        Delete all keys matching a pattern for a specific tenant and module.
        
        Uses SCAN (not KEYS) to avoid blocking Redis.
        
        Args:
            tenant_id: Tenant ID
            module: Module name
            pattern: Pattern to match (default: "*" for all keys in module)
        
        Returns:
            Number of keys deleted
        
        Example:
            delete_pattern(1, 'products', 'list:*')
            → Deletes: stock:tenant:1:products:list:*
        """
        if not self.is_available():
            return 0
        
        try:
            # Build full pattern with tenant isolation
            full_pattern = self._build_key(tenant_id, module, pattern)
            
            # Use SCAN to find keys (non-blocking)
            deleted_count = 0
            cursor = 0
            
            while True:
                cursor, keys = self.client.scan(cursor, match=full_pattern, count=100)
                
                if keys:
                    # Delete in pipeline for efficiency
                    pipeline = self.client.pipeline()
                    for key in keys:
                        pipeline.delete(key)
                    pipeline.execute()
                    deleted_count += len(keys)
                
                if cursor == 0:
                    break
            
            if deleted_count > 0:
                logger.info(f"[CACHE] INVALIDATE: {full_pattern} ({deleted_count} keys)")
            
            return deleted_count
            
        except RedisError as e:
            logger.warning(f"[CACHE] ✗ Delete pattern error: {e}")
            return 0
    
    def memoize(
        self,
        tenant_id: int,
        module: str,
        key: str,
        loader_fn: Callable[[], Any],
        ttl: int = None
    ) -> Any:
        """
        Cache-aside pattern: get from cache, or load and cache.
        
        Args:
            tenant_id: Tenant ID
            module: Module name
            key: Cache key
            loader_fn: Function to call if cache miss (no args)
            ttl: TTL in seconds
        
        Returns:
            Cached value or freshly loaded value
        
        Example:
            def load_products():
                return db.query(Product).filter_by(tenant_id=1).all()
            
            products = cache.memoize(1, 'products', 'list', load_products, ttl=60)
        """
        # Try cache first
        cached = self.get(tenant_id, module, key)
        if cached is not None:
            return cached
        
        # Cache miss: load from source
        try:
            value = loader_fn()
            
            # Cache for next time
            self.set(tenant_id, module, key, value, ttl)
            
            return value
            
        except Exception as e:
            logger.exception(f"[CACHE] ✗ Loader function error: {e}")
            raise
    
    def invalidate_module(self, tenant_id: int, module: str) -> int:
        """
        Invalidate all cache for a specific tenant and module.
        
        Args:
            tenant_id: Tenant ID
            module: Module name (e.g., 'products', 'categories')
        
        Returns:
            Number of keys deleted
        
        Example:
            invalidate_module(1, 'products')
            → Deletes all: stock:tenant:1:products:*
        """
        return self.delete_pattern(tenant_id, module, "*")


# Singleton instance
_cache_service: Optional[CacheService] = None


def init_cache(app):
    """
    Initialize cache service with Flask app.
    
    Args:
        app: Flask application instance
    """
    global _cache_service
    _cache_service = CacheService(app)
    
    # Store in app.extensions for easy access
    if not hasattr(app, 'extensions'):
        app.extensions = {}
    app.extensions['cache'] = _cache_service


def get_cache() -> CacheService:
    """
    Get cache service instance.
    
    Returns:
        CacheService instance
    
    Raises:
        RuntimeError: If cache not initialized
    """
    if _cache_service is None:
        raise RuntimeError("Cache not initialized. Call init_cache(app) first.")
    return _cache_service
