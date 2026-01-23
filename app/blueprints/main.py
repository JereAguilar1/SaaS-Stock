"""Main blueprint with health check endpoints."""
from flask import Blueprint, jsonify
from sqlalchemy import text
from app.database import get_session

main_bp = Blueprint('main', __name__)


# Note: Root route (/) is now handled by auth blueprint (MEJORA 8)


@main_bp.route('/health')
def health():
    """
    Health check endpoint that validates database connection.
    
    Returns:
        200: Healthy (DB connected)
        500: Unhealthy (DB error)
    """
    try:
        session = get_session()
        # Execute simple query to test connection
        result = session.execute(text("SELECT 1 as health_check"))
        row = result.fetchone()
        
        if row and row[0] == 1:
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'message': 'Database connection successful'
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'error',
                'message': 'Unexpected query result'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'message': 'Failed to connect to database'
        }), 500


@main_bp.route('/health/cache')
def health_cache():
    """
    Cache health check endpoint (PASO 8).
    
    Validates Redis connection and cache service availability.
    
    Returns:
        200: Cache OK or Degraded (app continues without cache)
        
    Note:
        This endpoint NEVER returns 500, as cache is optional.
        If Redis is down, status is "degraded" but app continues.
    """
    try:
        from app.services.cache_service import get_cache
        cache = get_cache()
        
        if cache.is_available():
            # Try a test operation
            test_key = "health_check"
            cache.set(0, "system", test_key, {"test": "ok"}, ttl=10)
            result = cache.get(0, "system", test_key)
            
            if result and result.get('test') == 'ok':
                return jsonify({
                    'status': 'ok',
                    'cache': 'connected',
                    'redis': 'healthy',
                    'message': 'Cache is working correctly'
                }), 200
            else:
                return jsonify({
                    'status': 'degraded',
                    'cache': 'error',
                    'redis': 'connected_but_failing',
                    'message': 'Redis connected but operations failing'
                }), 200
        else:
            return jsonify({
                'status': 'degraded',
                'cache': 'unavailable',
                'redis': 'disconnected',
                'message': 'Cache disabled or Redis unavailable (app continues without cache)'
            }), 200
            
    except Exception as e:
        return jsonify({
            'status': 'degraded',
            'cache': 'error',
            'redis': 'unknown',
            'error': str(e),
            'message': 'Cache health check failed (app continues without cache)'
        }), 200

