"""Billing gate middleware - blocks access if subscription is not active."""
import os
import threading
import time
from flask import g, redirect, url_for, flash, request
from app.database import get_session
from app.models import MPSubscription


# Cache simple en memoria (thread-safe)
_cache_lock = threading.Lock()
_subscription_cache = {}
_CACHE_TTL = 30  # segundos


def is_billing_enabled():
    """Check if billing is enabled via environment variable."""
    return os.getenv('BILLING_ENABLED', 'false').lower() == 'true'


def is_public_route(path: str) -> bool:
    """
    Determinar si una ruta es pública (no requiere suscripción activa).
    
    Args:
        path: Request path
    
    Returns:
        True si es ruta pública
    """
    public_prefixes = [
        '/auth/',
        '/billing/',
        '/webhooks/',
        '/health',
        '/static/',
        '/favicon.ico',
        # Admin panel (separado del billing de tenants)
        '/admin/',
    ]
    
    for prefix in public_prefixes:
        if path.startswith(prefix):
            return True
    
    return False


def get_cached_subscription_status(tenant_id: int) -> str:
    """
    Obtener estado de suscripción con cache de 30s.
    
    Args:
        tenant_id: ID del tenant
    
    Returns:
        Status string o None
    """
    with _cache_lock:
        # Verificar cache
        cache_entry = _subscription_cache.get(tenant_id)
        if cache_entry:
            cached_status, cached_at = cache_entry
            if time.time() - cached_at < _CACHE_TTL:
                return cached_status
    
    # Cache miss o expirado - consultar DB
    db_session = get_session()
    subscription = db_session.query(MPSubscription).filter(
        MPSubscription.tenant_id == tenant_id
    ).order_by(MPSubscription.created_at.desc()).first()
    
    status = subscription.status if subscription else None
    
    # Actualizar cache
    with _cache_lock:
        _subscription_cache[tenant_id] = (status, time.time())
    
    return status


def check_billing_gate():
    """
    Middleware para verificar suscripción activa antes de cada request.
    
    Si el tenant no tiene suscripción ACTIVE, redirige a /billing/plans
    excepto para rutas públicas.
    """
    # Si billing no está habilitado, permitir todo
    if not is_billing_enabled():
        return
    
    # Rutas públicas siempre permitidas
    if is_public_route(request.path):
        return
    
    # Si no hay tenant seleccionado, no aplicar gating
    # (el middleware de tenant se encargará)
    if not hasattr(g, 'tenant_id') or not g.tenant_id:
        return
    
    # Verificar estado de suscripción
    status = get_cached_subscription_status(g.tenant_id)
    
    if status != 'ACTIVE':
        # Suscripción no activa - bloquear acceso
        flash(
            'Tu suscripción no está activa. Por favor, verifica tu estado de pago.',
            'warning'
        )
        return redirect(url_for('billing.plans'))
    
    # Suscripción activa - permitir acceso
    return
