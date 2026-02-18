"""
Mercado Pago Service for Subscription Management.
Handles interaction with Mercado Pago API for Plans and Subscriptions (Preapproval).
"""

import logging
from typing import Dict, Any, Optional
from flask import current_app
import mercadopago  # type: ignore

logger = logging.getLogger(__name__)

class MercadoPagoService:
    """Service to interact with Mercado Pago API."""

    def __init__(self, access_token: Optional[str] = None):
        """Initialize SDK with access token."""
        self.token = access_token or current_app.config.get('MP_ACCESS_TOKEN')
        if not self.token:
            logger.warning("Mercado Pago ACCESS_TOKEN not found in config.")
            self.sdk = None
        else:
            self.sdk = mercadopago.SDK(self.token)

    def _check_sdk(self):
        """Raise error if SDK is not initialized."""
        if not self.sdk:
            raise ValueError("Mercado Pago SDK not initialized. Missing MP_ACCESS_TOKEN.")

    def create_plan(self, reason: str, auto_recurring: Dict[str, Any], back_url: str) -> Dict[str, Any]:
        """
        Create a customized subscription plan (Preapproval Plan).
        
        Args:
            reason (str): Description/Title of the plan (e.g. "Plan Pro Mensual").
            auto_recurring (dict): Recurrence details.
                pool_id (int): ID of the wallet/user receiving money? (usually not needed for basic)
                frequency (int): e.g. 1
                frequency_type (str): 'months' or 'days'
                transaction_amount (float): Amount to charge.
                currency_id (str): 'ARS', etc.
            back_url (str): URL to redirect after subscription.
            
        Returns:
            dict: The API response with plan details (id, init_point, etc).
        """
        self._check_sdk()
        
        plan_data = {
            "reason": reason,
            "auto_recurring": auto_recurring,
            "back_url": back_url,
            "status": "active"
        }
        
        try:
            # The SDK method for plans is usually .preapproval_plan().create(data)
            # Verifying SDK structure: sdk.preapproval_plan() returns a manager.
            response = self.sdk.plan().create(plan_data)
            
            if response["status"] == 201:
                logger.info(f"MP Plan created successfully: {response['response']['id']}")
                return response["response"]
            else:
                logger.error(f"Error creating MP Plan: {response}")
                raise Exception(f"Failed to create plan: {response.get('response', 'Unknown error')}")
                
        except Exception as e:
            logger.exception("Exception creating Mercado Pago plan")
            raise e

    def update_plan(self, plan_id: str, new_amount: float) -> Dict[str, Any]:
        """
        Update a plan's transaction amount.
        Note: MP has restrictions on what can be updated.
        """
        self._check_sdk()
        
        data = {
            "auto_recurring": {
                "transaction_amount": new_amount
            }
        }
        
        try:
            response = self.sdk.plan().update(plan_id, data)
            
            if response["status"] == 200:
                logger.info(f"MP Plan updated: {plan_id}")
                return response["response"]
            else:
                logger.error(f"Error updating MP Plan {plan_id}: {response}")
                raise Exception(f"Failed to update plan: {response.get('response')}")
        
        except Exception as e:
            logger.exception(f"Exception updating plan {plan_id}")
            raise e

    def create_subscription(self, preapproval_plan_id: str, payer_email: str, external_reference: str, card_token_id: str = None) -> Dict[str, Any]:
        """
        Create a subscription (Preapproval) logic.
        ACTUALLY: For Plans, you usually send the user to the `init_point` of the Plan,
        OR you act on behalf of the user to subscribe them to a plan id.
        
        If we want to create a subscription link for a specific Plan, we usually just share the Plan's `init_point`.
        However, if we want to associate it programmatically:
        We create a 'preapproval' linking to 'preapproval_plan_id'.
        """
        self._check_sdk()
        
        data = {
            "preapproval_plan_id": preapproval_plan_id,
            "payer_email": payer_email,
            "external_reference": external_reference, # Important: Tenant ID or Subscription ID
            "status": "authorized"
        }
        
        if card_token_id:
             data["card_token_id"] = card_token_id

        try:
            response = self.sdk.preapproval().create(data)
            
            if response["status"] == 201:
                logger.info(f"MP Subscription created: {response['response']['id']}")
                return response["response"]
            else:
                # If 201 is not returned, it might be an error
                logger.error(f"Error creating subscription: {response}")
                raise Exception(f"Failed to create subscription: {response.get('response')}")

        except Exception as e:
            logger.exception("Exception creating subscription")
            raise e

    def get_subscription(self, preapproval_id: str) -> Dict[str, Any]:
        """Get subscription details."""
        self._check_sdk()
        try:
            response = self.sdk.preapproval().get(preapproval_id)
            if response["status"] == 200:
                return response["response"]
            else:
                logger.error(f"Error fetching subscription {preapproval_id}: {response}")
                return None
        except Exception as e:
            logger.exception(f"Exception fetching subscription {preapproval_id}")
            raise e
            
    def search_subscription_by_reference(self, external_reference: str) -> Optional[Dict[str, Any]]:
        """
        Search for a subscription by external_reference (our local tenant_id/sub_id).
        """
        self._check_sdk()
        filters = {
            "external_reference": external_reference
        }
        try:
            response = self.sdk.preapproval().search(filters)
            if response["status"] == 200:
                results = response["response"]["results"]
                if results:
                    return results[0]  # Return the most recent or relevant
                return None
            else:
                logger.error(f"Error searching subscription: {response}")
                return None
        except Exception as e:
            logger.exception("Exception searching subscription")
            raise e

    def create_subscription_preference(self, plan_id: str, payer_email: str, external_reference: str, back_url: str, reason: str) -> str:
        """
        Create a subscription 'intent' and return the init_point.
        This actually creates a Preapproval (subscription) in MP and returns the link for the user.
        """
        self._check_sdk()
        
        data = {
            "preapproval_plan_id": plan_id,
            "payer_email": payer_email,
            "external_reference": external_reference,
            "back_url": back_url,
            "reason": reason,
            "status": "pending"
        }
        
        try:
            response = self.sdk.preapproval().create(data)
            if response["status"] == 201:
                return response["response"]["init_point"]
            else:
                logger.error(f"Error creating subscription preference: {response}")
                raise Exception(f"Failed to create subscription preference: {response.get('response')}")
        except Exception as e:
            logger.exception("Exception creating subscription preference")
            raise e
