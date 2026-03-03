"""
Script de importación de productos desde CSV.
Importa productos al Tenant 17.
"""
import csv
import os
from decimal import Decimal

from app import create_app
from app.database import get_session
from app.models.product import Product
from app.models.uom import UOM

# ==========================================
# CONFIGURACIÓN (Modificar antes de ejecutar)
TENANT_ID = 17
ARCHIVO_CSV = 'Hoja de cálculo sin título - Hoja1.csv'
# ==========================================


def clean_price(val_str):
    """Limpia el string de precio del CSV y retorna Decimal."""
    if not val_str:
        return Decimal('0.00')
    clean_str = str(val_str).replace('"', '').replace(',', '').strip()
    try:
        return Decimal(clean_str)
    except Exception:
        return Decimal('0.00')


def run_import():
    app = create_app()

    with app.app_context():
        session = get_session()

        # Obtener unidad de medida del tenant
        uom = session.query(UOM).filter_by(tenant_id=TENANT_ID).first()
        if not uom:
            print("❌ Error: No hay UOM en este tenant.")
            return

        # Verificar que el archivo CSV existe
        if not os.path.isfile(ARCHIVO_CSV):
            print(f"❌ Error: No se encontró '{ARCHIVO_CSV}'")
            print(f"   Ubicación esperada: {os.path.abspath(ARCHIVO_CSV)}")
            return

        with open(ARCHIVO_CSV, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            print(f"📋 Columnas detectadas en el CSV: {reader.fieldnames}")
            print(f"🏢 Importando al Tenant ID: {TENANT_ID}")
            print("-" * 50)

            productos_creados = 0
            errores = 0

            for i, row in enumerate(reader, start=2):
                codigo = row.get('Código', row.get('Codigo', '')).strip()
                nombre = row.get('Artículo', row.get('Articulo', '')).strip()
                precio_str = row.get('VTA', '0')

                if not nombre:
                    print(f"  ⚠️  Fila {i}: Sin nombre, saltando...")
                    continue

                precio_limpio = clean_price(precio_str)

                try:
                    nuevo_producto = Product(
                        tenant_id=TENANT_ID,
                        name=nombre,
                        sku=codigo if codigo else None,
                        sale_price=precio_limpio,
                        cost=Decimal('0.00'),
                        uom_id=uom.id,
                        active=True,
                    )
                    session.add(nuevo_producto)
                    productos_creados += 1
                    print(f"  ✅ Producto: {nombre} | Código: {codigo} | Precio: ${precio_limpio}")
                except Exception as e:
                    errores += 1
                    print(f"  ❌ Error en fila {i} ({nombre}): {e}")
                    session.rollback()
                    continue

            # Guardar todo
            try:
                session.commit()
                print("-" * 50)
                print(f"🎉 ¡Importación completada!")
                print(f"   Productos creados: {productos_creados}")
                print(f"   Errores: {errores}")
                print(f"   Tenant: {TENANT_ID}")
            except Exception as e:
                session.rollback()
                print(f"❌ Error al guardar en la base de datos: {e}")


if __name__ == '__main__':
    run_import()
