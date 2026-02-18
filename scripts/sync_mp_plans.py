import os
import sys

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.database import get_session
from app.models.plan import Plan
from app.services.mercadopago_service import MercadoPagoService

def sync_plans():
    app = create_app()
    with app.app_context():
        session = get_session()
        mp_service = MercadoPagoService()
        
        # Obtener planes activos de la DB que no tienen ID de MP
        plans = session.query(Plan).filter(Plan.is_active == True).all()
        
        base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000')
        
        for plan in plans:
            if plan.mp_preapproval_plan_id:
                print(f"Plan '{plan.name}' ya tiene ID de MP: {plan.mp_preapproval_plan_id}")
                continue
                
            if plan.code == 'free':
                print(f"Omitiendo plan 'free' (no requiere MP)")
                continue

            print(f"Creando plan '{plan.name}' en Mercado Pago...")
            
            try:
                # Configuración de recurrencia (mensual)
                auto_recurring = {
                    "frequency": 1,
                    "frequency_type": "months",
                    "transaction_amount": float(plan.price),
                    "currency_id": plan.currency or "ARS"
                }
                
                # Crear el plan en MP
                # Mercado Pago requiere un init_point o back_url
                mp_plan = mp_service.create_plan(
                    reason=f"Suscripción {plan.name} - StockAR",
                    auto_recurring=auto_recurring,
                    back_url=f"{base_url}/settings/billing"
                )
                
                # Guardar el ID en nuestra DB
                plan.mp_preapproval_plan_id = mp_plan['id']
                session.commit()
                print(f"¡Éxito! Plan '{plan.name}' vinculado con MP ID: {plan.mp_preapproval_plan_id}")
                
            except Exception as e:
                import traceback
                print(f"Error vinculando plan '{plan.name}': {str(e)}")
                # traceback.print_exc()
                session.rollback()

if __name__ == "__main__":
    sync_plans()
