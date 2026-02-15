"""
Redis Cache Service for Multi-Tenant Application.
Provides tenant-isolated caching with graceful degradation.
"""

import logging
import json
from typing import Any, Optional, Callable, Dict, Union
from datetime import datetime, date
from decimal import Decimal

import redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError
from flask import Flask, current_app

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service with multi-tenant support.
    
    Keys pattern: {prefix}:tenant:{tenant_id}:{module}:{key}
    """
    
    def __init__(self, app: Optional[Flask] = None):
        """Initialize cache service."""
        self.client: Optional[redis.Redis] = None
        self._enabled: bool = False
        self._prefix: str = ""
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """Initialize Redis client from Flask app config."""
        self._enabled = app.config.get('CACHE_ENABLED', True)
        self._prefix = app.config.get('CACHE_KEY_PREFIX', 'stock')
        redis_url = app.config.get('REDIS_URL', 'redis://redis:6379/0')
        
        if not self._enabled:
            logger.info("[CACHE] Cache is DISABLED via config")
            return
        
        try:
            self.client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                socket_keepalive=True,
                max_connections=50,
                retry_on_timeout=True,
                health_check_interval=30
            )
            self.client.ping()
            logger.info(f"[CACHE] ✓ Redis connected: {redis_url}")
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"[CACHE] ⚠ Redis connection failed: {e}. Cache DISABLED.")
            self._enabled = False
            self.client = None
    
    def is_available(self) -> bool:
        """Check if cache is available and healthy."""
        if not self._enabled or not self.client:
            return False
        try:
            self.client.ping()
            return True
        except (ConnectionError, RedisError):
            return False
    
    def _build_key(self, tenant_id: int, module: str, key: str) -> str:
        """Build tenant-isolated cache key."""
        return f"{self._prefix}:tenant:{tenant_id}:{module}:{key}"
    
    def _serialize(self, value: Any) -> str:
        """Serialize Python object to JSON string with Decimal precision."""
        def default_handler(obj: Any) -> Any:
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                # Guardar como un diccionario especial para reconocerlo al deserializar si fuera necesario
                # O simplemente como string para máxima precisión.
                return {"__decimal__": str(obj)}
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        return json.dumps(value, default=default_handler)
    
    def _deserialize(self, value: str) -> Any:
        """Deserialize JSON string to Python object, reconstructing Decimals."""
        def object_hook(dct: Dict[str, Any]) -> Any:
            if "__decimal__" in dct:
                return Decimal(dct["__decimal__"])
            return dct
        return json.loads(value, object_hook=object_hook)
    
    def get(self, tenant_id: int, module: str, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.is_available():
            return None
        try:
            cache_key = self._build_key(tenant_id, module, key)
            value = self.client.get(cache_key)
            if value is None:
                return None
            return self._deserialize(value)
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"[CACHE] ✗ Get error: {e}")
            return None
    
    def set(self, tenant_id: int, module: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL."""
        if not self.is_available():
            return False
        try:
            cache_key = self._build_key(tenant_id, module, key)
            serialized = self._serialize(value)
            if ttl is None:
                ttl = current_app.config.get('CACHE_DEFAULT_TTL', 60)
            self.client.setex(cache_key, ttl, serialized)
            return True
        except (RedisError, TypeError) as e:
            logger.warning(f"[CACHE] ✗ Set error: {e}")
            return False
    
    def delete(self, tenant_id: int, module: str, key: str) -> bool:
        """Delete specific key from cache."""
        if not self.is_available():
            return False
        try:
            cache_key = self._build_key(tenant_id, module, key)
            self.client.delete(cache_key)
            return True
        except RedisError as e:
            logger.warning(f"[CACHE] ✗ Delete error: {e}")
            return False
    
    def delete_pattern(self, tenant_id: int, module: str, pattern: str = "*") -> int:
        """Delete all keys matching a pattern for a tenant/module."""
        if not self.is_available():
            return 0
        try:
            full_pattern = self._build_key(tenant_id, module, pattern)
            deleted_count = 0
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=full_pattern, count=100)
                if keys:
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
            logger.warning(f"[CACHE] ✗ Invalidate error: {e}")
            return 0
    
    def memoize(self, tenant_id: int, module: str, key: str, loader_fn: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """Cache-aside pattern: get from cache, or load and cache."""
        cached = self.get(tenant_id, module, key)
        if cached is not None:
            return cached
        try:
            value = loader_fn()
            self.set(tenant_id, module, key, value, ttl)
            return value
        except Exception as e:
            logger.exception(f"[CACHE] ✗ Loader error: {e}")
            raise
    
    def invalidate_module(self, tenant_id: int, module: str) -> int:
        """Invalidate all cache for a module."""
        return self.delete_pattern(tenant_id, module, "*")


_cache_service: Optional[CacheService] = None

def init_cache(app: Flask) -> None:
    """Initialize cache service singleton."""
    global _cache_service
    _cache_service = CacheService(app)
    if not hasattr(app, 'extensions'):
        app.extensions = {}
    app.extensions['cache'] = _cache_service

def get_cache() -> CacheService:
    """Get cache service instance."""
    if _cache_service is None:
        raise RuntimeError("Cache not initialized.")
    return _cache_service
