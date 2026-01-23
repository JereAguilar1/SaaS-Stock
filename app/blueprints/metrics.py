"""
Prometheus metrics blueprint for observability (PASO 9).

Exposes /metrics endpoint with application and HTTP request metrics.
This endpoint should be restricted to internal network or monitoring systems only.
"""
from flask import Blueprint, Response, request, g
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from prometheus_client import multiprocess, REGISTRY
import time
import os

metrics_bp = Blueprint('metrics', __name__)

# Check if running in multi-process mode (Gunicorn)
MULTIPROCESS_MODE = os.environ.get('PROMETHEUS_MULTIPROC_DIR') is not None

# Use multiprocess registry in production with Gunicorn
if MULTIPROCESS_MODE:
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
else:
    registry = REGISTRY

# HTTP Request Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'http_status'],
    registry=registry if not MULTIPROCESS_MODE else None
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    registry=registry if not MULTIPROCESS_MODE else None,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

http_requests_in_flight = Gauge(
    'http_requests_in_flight',
    'Number of HTTP requests currently being processed',
    registry=registry if not MULTIPROCESS_MODE else None
)


def setup_metrics_instrumentation(app):
    """
    Setup before_request and after_request hooks for automatic metrics collection.
    
    This should be called from app factory after app creation.
    """
    
    @app.before_request
    def before_request_metrics():
        """Record request start time and increment in-flight counter."""
        g._prometheus_metrics_start_time = time.time()
        http_requests_in_flight.inc()
    
    @app.after_request
    def after_request_metrics(response):
        """Record request metrics after response is ready."""
        try:
            # Calculate request duration
            if hasattr(g, '_prometheus_metrics_start_time'):
                duration = time.time() - g._prometheus_metrics_start_time
                
                # Get endpoint name (e.g., 'catalog.products_list')
                endpoint = request.endpoint or 'unknown'
                method = request.method
                status = response.status_code
                
                # Record metrics
                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(duration)
                
                http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    http_status=status
                ).inc()
                
                http_requests_in_flight.dec()
        except Exception as e:
            # Don't break request flow if metrics fail
            app.logger.warning(f"Failed to record metrics: {e}")
        
        return response


@metrics_bp.route('/metrics')
def metrics():
    """
    Prometheus metrics endpoint.
    
    SECURITY NOTE:
    - This endpoint is NOT authenticated
    - Should be restricted by network/firewall rules in production
    - Do not expose publicly - only allow access from Prometheus server
    - Consider adding IP allowlist or internal network restriction
    
    Returns:
        Response: Prometheus-formatted metrics in text/plain
    """
    if MULTIPROCESS_MODE:
        # In multi-process mode, collect from all workers
        data = generate_latest(registry)
    else:
        # In single-process mode, use default registry
        data = generate_latest(REGISTRY)
    
    return Response(data, mimetype=CONTENT_TYPE_LATEST)
