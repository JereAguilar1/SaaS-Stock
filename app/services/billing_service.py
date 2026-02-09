"""Billing service for managing subscriptions and webhooks."""
import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from flask import current_app
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import BillingPlan, MPSubscription, MPWebhookEvent, Tenant
from app.services.mercadopago_client import MercadoPagoClient


class BillingService:
    """Servicio de facturación con Mercado Pago."""
    
    def __init__(self, db_session: Session):
        """
        Initialize billing service.
        
        Args:
            db_session: SQLAlchemy session
        """
        self.db = db_session
        self.mp_client = MercadoPagoClient()
    
    def create_subscription(
        self,
        tenant_id: int,
        plan_code: str,
        payer_email: str
    ) -> MPSubscription:
        """
        Crear suscripción para un tenant.
        
        Args:
            tenant_id: ID del tenant
            plan_code: Código del plan (ej: PRO)
            payer_email: Email del pagador
        
        Returns:
            MPSubscription creada
        
        Raises:
            ValueError: Si ya existe suscripción activa o plan no encontrado
        """
        # Verificar que no exista suscripción activa o pendiente
        existing = self.db.query(MPSubscription).filter(
            MPSubscription.tenant_id == tenant_id,
            MPSubscription.status.in_(['ACTIVE', 'PENDING'])
        ).first()
        
        if existing:
            raise ValueError(
                f"Ya existe una suscripción {existing.status} para este negocio"
            )
        
        # Obtener plan
        plan = self.db.query(BillingPlan).filter(
            BillingPlan.code == plan_code,
            BillingPlan.active == True
        ).first()
        
        if not plan:
            raise ValueError(f"Plan '{plan_code}' no encontrado o inactivo")
        
        # Obtener tenant para nombre
        tenant = self.db.query(Tenant).get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} no encontrado")
        
        # Crear preapproval en MP
        app_base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000')
        back_url = f"{app_base_url}/billing/return"
        
        try:
            mp_response = self.mp_client.create_preapproval(
                reason=f"Suscripción SaaS Stock - {tenant.name}",
                external_reference=str(tenant_id),
                payer_email=payer_email,
                transaction_amount=float(plan.price_amount),
                currency_id=plan.currency,
                frequency=plan.frequency,
                frequency_type=plan.frequency_type,
                back_url=back_url
            )
        except Exception as e:
            current_app.logger.error(f"[BILLING] Error creating MP preapproval: {e}")
            raise ValueError(f"Error al crear suscripción en Mercado Pago: {str(e)}")
        
        # Crear registro de suscripción
        subscription = MPSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status='PENDING',
            mp_preapproval_id=mp_response.get('id'),
            mp_init_point=mp_response.get('init_point'),
            metadata_json={
                'payer_email': payer_email,
                'mp_response': mp_response
            }
        )
        
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        
        current_app.logger.info(
            f"[BILLING] Subscription created for tenant {tenant_id}: {subscription.id}"
        )
        
        return subscription
    
    def process_webhook(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Procesar evento webhook de Mercado Pago (idempotente).
        
        Args:
            topic: Tipo de evento (preapproval, payment, etc)
            payload: Payload del webhook
        
        Returns:
            True si se procesó correctamente, False si ya existía
        
        Raises:
            Exception: Si hay error al procesar
        """
        # Generar dedupe_key
        mp_event_id = payload.get('id')
        resource_id = payload.get('data', {}).get('id')
        
        dedupe_components = [
            topic,
            str(mp_event_id) if mp_event_id else '',
            str(resource_id) if resource_id else '',
            json.dumps(payload, sort_keys=True)
        ]
        dedupe_str = ':'.join(dedupe_components)
        dedupe_key = hashlib.sha256(dedupe_str.encode()).hexdigest()
        
        # Verificar si ya existe
        existing = self.db.query(MPWebhookEvent).filter(
            MPWebhookEvent.dedupe_key == dedupe_key
        ).first()
        
        if existing:
            current_app.logger.info(
                f"[BILLING] Webhook already processed: {dedupe_key[:16]}..."
            )
            return False
        
        # Crear registro de webhook
        webhook_event = MPWebhookEvent(
            topic=topic,
            mp_event_id=str(mp_event_id) if mp_event_id else None,
            resource_id=str(resource_id) if resource_id else None,
            payload_json=payload,
            dedupe_key=dedupe_key,
            status='PROCESSING'
        )
        
        try:
            self.db.add(webhook_event)
            self.db.commit()
        except IntegrityError:
            # Race condition: otro proceso ya lo procesó
            self.db.rollback()
            current_app.logger.warning(
                f"[BILLING] Webhook dedupe conflict (race): {dedupe_key[:16]}..."
            )
            return False
        
        # Procesar según topic
        try:
            if topic == 'preapproval':
                self._process_preapproval_webhook(resource_id, webhook_event)
            else:
                current_app.logger.warning(f"[BILLING] Unknown topic: {topic}")
            
            # Marcar como procesado
            webhook_event.status = 'PROCESSED'
            webhook_event.processed_at = datetime.utcnow()
            self.db.commit()
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"[BILLING] Error processing webhook: {e}")
            webhook_event.status = 'FAILED'
            self.db.commit()
            raise
    
    def _process_preapproval_webhook(
        self,
        preapproval_id: str,
        webhook_event: MPWebhookEvent
    ):
        """Procesar webhook de preapproval."""
        if not preapproval_id:
            current_app.logger.warning("[BILLING] No preapproval_id in webhook")
            return
        
        # Consultar estado real en MP
        try:
            mp_data = self.mp_client.get_preapproval(preapproval_id)
        except Exception as e:
            current_app.logger.error(
                f"[BILLING] Error fetching preapproval from MP: {e}"
            )
            raise
        
        mp_status = mp_data.get('status', '').lower()
        
        # Mapear status de MP a nuestro sistema
        status_map = {
            'authorized': 'ACTIVE',
            'pending': 'PENDING',
            'paused': 'PAUSED',
            'cancelled': 'CANCELED',
            'rejected': 'REJECTED',
            'expired': 'EXPIRED'
        }
        
        new_status = status_map.get(mp_status, 'PENDING')
        
        # Actualizar suscripción
        subscription = self.db.query(MPSubscription).filter(
            MPSubscription.mp_preapproval_id == preapproval_id
        ).first()
        
        if not subscription:
            current_app.logger.warning(
                f"[BILLING] Subscription not found for preapproval: {preapproval_id}"
            )
            return
        
        old_status = subscription.status
        subscription.status = new_status
        subscription.updated_at = datetime.utcnow()
        
        # Actualizar fechas según estado
        if new_status == 'ACTIVE' and not subscription.started_at:
            subscription.started_at = datetime.utcnow()
        elif new_status in ['CANCELED', 'REJECTED', 'EXPIRED'] and not subscription.cancelled_at:
            subscription.cancelled_at = datetime.utcnow()
        
        # Actualizar metadata
        subscription.metadata_json['last_mp_status'] = mp_status
        subscription.metadata_json['last_webhook_at'] = datetime.utcnow().isoformat()
        
        self.db.commit()
        
        current_app.logger.info(
            f"[BILLING] Subscription {subscription.id} updated: "
            f"{old_status} -> {new_status} (tenant {subscription.tenant_id})"
        )
    
    def get_tenant_subscription_status(self, tenant_id: int) -> Optional[str]:
        """
        Obtener estado de suscripción de un tenant.
        
        Args:
            tenant_id: ID del tenant
        
        Returns:
            Status string o None si no tiene suscripción
        """
        subscription = self.db.query(MPSubscription).filter(
            MPSubscription.tenant_id == tenant_id
        ).order_by(MPSubscription.created_at.desc()).first()
        
        return subscription.status if subscription else None
    
    def is_tenant_active(self, tenant_id: int) -> bool:
        """
        Verificar si un tenant tiene suscripción activa.
        
        Args:
            tenant_id: ID del tenant
        
        Returns:
            True si tiene suscripción ACTIVE
        """
        status = self.get_tenant_subscription_status(tenant_id)
        return status == 'ACTIVE'
