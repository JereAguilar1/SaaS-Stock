"""Mercado Pago API Client for subscription management."""
import os
import requests
from typing import Dict, Any, Optional
from flask import current_app


class MercadoPagoClient:
    """Cliente para interactuar con la API de Mercado Pago."""
    
    BASE_URL = "https://api.mercadopago.com"
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Mercado Pago client.
        
        Args:
            access_token: MP access token. If None, reads from env MP_ACCESS_TOKEN
        """
        self.access_token = access_token or os.getenv('MP_ACCESS_TOKEN')
        if not self.access_token:
            raise ValueError("MP_ACCESS_TOKEN is required")
        
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def create_preapproval(
        self,
        reason: str,
        external_reference: str,
        payer_email: str,
        transaction_amount: float,
        currency_id: str = 'ARS',
        frequency: int = 1,
        frequency_type: str = 'months',
        back_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crear suscripción (preapproval) en Mercado Pago.
        
        Args:
            reason: Descripción de la suscripción
            external_reference: Referencia externa (tenant_id)
            payer_email: Email del pagador
            transaction_amount: Monto a cobrar
            currency_id: Moneda (default: ARS)
            frequency: Frecuencia de cobro
            frequency_type: Tipo de frecuencia (months, days)
            back_url: URL de retorno después del pago
        
        Returns:
            Dict con respuesta de MP incluyendo init_point y preapproval_id
        
        Raises:
            requests.HTTPError: Si la API de MP devuelve error
        """
        url = f"{self.BASE_URL}/preapproval"
        
        payload = {
            "reason": reason,
            "external_reference": str(external_reference),
            "payer_email": payer_email,
            "auto_recurring": {
                "frequency": frequency,
                "frequency_type": frequency_type,
                "transaction_amount": transaction_amount,
                "currency_id": currency_id
            },
            "status": "pending"
        }
        
        if back_url:
            payload["back_url"] = back_url
        
        current_app.logger.info(f"[MP] Creating preapproval for {external_reference}")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current_app.logger.info(
                f"[MP] Preapproval created: {data.get('id')} - init_point: {data.get('init_point')}"
            )
            
            return data
            
        except requests.HTTPError as e:
            current_app.logger.error(f"[MP] Error creating preapproval: {e.response.text}")
            raise
        except Exception as e:
            current_app.logger.error(f"[MP] Unexpected error: {str(e)}")
            raise
    
    def get_preapproval(self, preapproval_id: str) -> Dict[str, Any]:
        """
        Consultar estado de una suscripción (preapproval).
        
        Args:
            preapproval_id: ID del preapproval en MP
        
        Returns:
            Dict con datos del preapproval
        
        Raises:
            requests.HTTPError: Si la API de MP devuelve error
        """
        url = f"{self.BASE_URL}/preapproval/{preapproval_id}"
        
        current_app.logger.info(f"[MP] Getting preapproval: {preapproval_id}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current_app.logger.info(
                f"[MP] Preapproval status: {data.get('status')} - {preapproval_id}"
            )
            
            return data
            
        except requests.HTTPError as e:
            current_app.logger.error(f"[MP] Error getting preapproval: {e.response.text}")
            raise
        except Exception as e:
            current_app.logger.error(f"[MP] Unexpected error: {str(e)}")
            raise
    
    def cancel_preapproval(self, preapproval_id: str) -> Dict[str, Any]:
        """
        Cancelar una suscripción (preapproval).
        
        Args:
            preapproval_id: ID del preapproval en MP
        
        Returns:
            Dict con respuesta de MP
        
        Raises:
            requests.HTTPError: Si la API de MP devuelve error
        """
        url = f"{self.BASE_URL}/preapproval/{preapproval_id}"
        
        payload = {"status": "cancelled"}
        
        current_app.logger.info(f"[MP] Cancelling preapproval: {preapproval_id}")
        
        try:
            response = requests.put(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current_app.logger.info(f"[MP] Preapproval cancelled: {preapproval_id}")
            
            return data
            
        except requests.HTTPError as e:
            current_app.logger.error(f"[MP] Error cancelling preapproval: {e.response.text}")
            raise
        except Exception as e:
            current_app.logger.error(f"[MP] Unexpected error: {str(e)}")
            raise
