"""
Script de importación de clientes desde CSV.
Importa clientes y genera ventas fantasma para saldos pendientes.
"""
import csv
import os
from decimal import Decimal

from app import create_app
from app.database import db_session, init_db
from app.models.customer import Customer
from app.models.sale import Sale, SaleStatus

# ==========================================
# CONFIGURACIÓN (Modificar antes de ejecutar)
TENANT_ID = 17  # <-- REEMPLAZAR POR EL ID DE LA EMPRESA
ARCHIVO_CSV = 'clientes app - Hoja1.csv'
# ==========================================


def clean_balance(val_str):
    """
    Limpia el string de saldo del CSV.
    Maneja formatos como: "536,467.65" o 536467.65 o vacío.
    Retorna Decimal >= 0 (saldos negativos se convierten a 0).
    """
    if not val_str:
        return Decimal('0.00')

    # Limpiamos comillas dobles y espacios
    clean_str = str(val_str).replace('"', '').strip()

    # Removemos comas de miles (formato anglosajón: 536,467.65)
    clean_str = clean_str.replace(',', '')

    try:
        monto = Decimal(clean_str)
        # Si es negativo, devolvemos 0
        return monto if monto > 0 else Decimal('0.00')
    except Exception:
        return Decimal('0.00')


def run_import():
    app = create_app()

    with app.app_context():
        # Verificar que el archivo CSV existe
        if not os.path.isfile(ARCHIVO_CSV):
            print(f"❌ Error: No se encontró el archivo '{ARCHIVO_CSV}'")
            print(f"   Ubicación esperada: {os.path.abspath(ARCHIVO_CSV)}")
            return

        with open(ARCHIVO_CSV, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # Mostrar columnas detectadas para debug
            print(f"📋 Columnas detectadas en el CSV: {reader.fieldnames}")
            print(f"🏢 Importando al Tenant ID: {TENANT_ID}")
            print("-" * 50)

            clientes_creados = 0
            ventas_creadas = 0
            errores = 0

            for i, row in enumerate(reader, start=2):  # start=2 porque fila 1 es header
                codigo = row.get('Código', row.get('Codigo', '')).strip()
                nombre = row.get('Nombre', '').strip()
                saldo_str = row.get('Saldo total', row.get('Saldo Total', '0'))

                if not nombre:
                    print(f"  ⚠️  Fila {i}: Sin nombre, saltando...")
                    continue

                saldo_real = clean_balance(saldo_str)

                try:
                    # 1. Crear el cliente
                    nuevo_cliente = Customer(
                        tenant_id=TENANT_ID,
                        name=nombre,
                        tax_id=codigo if codigo else None,  # "Código" -> tax_id
                    )
                    db_session.add(nuevo_cliente)
                    db_session.flush()  # Para obtener el ID generado

                    clientes_creados += 1

                    # 2. Crear Venta Fantasma si hay saldo > 0
                    if saldo_real > 0:
                        venta_fantasma = Sale(
                            tenant_id=TENANT_ID,
                            customer_id=nuevo_cliente.id,
                            total=saldo_real,
                            amount_paid=Decimal('0.00'),
                            status=SaleStatus.CONFIRMED,
                            payment_status='pending',
                        )
                        db_session.add(venta_fantasma)
                        ventas_creadas += 1
                        print(f"  ✅ {nombre} (código: {codigo}) — saldo: ${saldo_real}")
                    else:
                        print(f"  ✅ {nombre} (código: {codigo}) — sin saldo")

                except Exception as e:
                    errores += 1
                    print(f"  ❌ Fila {i} ({nombre}): Error — {e}")
                    db_session.rollback()
                    continue

            # Guardar todo
            try:
                db_session.commit()
                print("-" * 50)
                print(f"🎉 ¡Importación completada!")
                print(f"   Clientes creados: {clientes_creados}")
                print(f"   Ventas fantasma (saldos): {ventas_creadas}")
                print(f"   Errores: {errores}")
                print(f"   Tenant: {TENANT_ID}")
            except Exception as e:
                db_session.rollback()
                print(f"❌ Error al guardar en la base de datos: {e}")


if __name__ == '__main__':
    run_import()
