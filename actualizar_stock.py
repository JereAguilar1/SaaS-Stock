"""
Script para marcar todos los productos del Tenant 17 como stock ilimitado.
Permite vender sin restricción de stock.
"""
from app import create_app
from app.database import get_session
from app.models.product import Product

TENANT_ID = 17


def run_update():
    app = create_app()

    with app.app_context():
        session = get_session()

        productos = session.query(Product).filter_by(tenant_id=TENANT_ID).all()

        for producto in productos:
            producto.is_unlimited_stock = True

        try:
            session.commit()
            print(f"🎉 ¡Listo! Se actualizaron {len(productos)} productos con stock ilimitado.")
        except Exception as e:
            session.rollback()
            print(f"❌ Error al guardar: {e}")


if __name__ == '__main__':
    run_update()
