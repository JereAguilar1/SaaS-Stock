"""Invoice service with transactional logic - Multi-Tenant."""

from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import (
    Product, Supplier, PurchaseInvoice, PurchaseInvoiceLine,
    StockMove, StockMoveLine,
    InvoiceStatus, StockMoveType, StockReferenceType
)
from app.exceptions import BusinessLogicError, NotFoundError


def create_invoice_with_lines(payload: Dict[str, Any], session: Session) -> int:
    """
    Create purchase invoice with lines and update stock (tenant-scoped).
    """
    try:
        session.begin_nested()
        
        tenant_id = payload.get('tenant_id')
        if not tenant_id:
            raise BusinessLogicError('tenant_id es requerido')
        
        supplier_id = payload.get('supplier_id')
        if not supplier_id:
            raise BusinessLogicError('El proveedor es requerido')
        
        supplier = session.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.tenant_id == tenant_id
        ).first()
        
        if not supplier:
            raise NotFoundError(f'Proveedor #{supplier_id} no encontrado.')
        
        invoice_number = payload.get('invoice_number', '').strip()
        if not invoice_number:
            raise BusinessLogicError('Número de boleta requerido.')
        
        invoice_date = payload.get('invoice_date')
        if not invoice_date:
            raise BusinessLogicError('Fecha de boleta requerida.')
        
        lines_data = payload.get('lines', [])
        if not lines_data:
            raise BusinessLogicError('Debe agregar al menos un ítem.')

        # 1. Batch Fetch Products
        prod_ids = [int(l['product_id']) for l in lines_data]
        products = session.query(Product).filter(
            Product.id.in_(prod_ids),
            Product.tenant_id == tenant_id
        ).all()
        products_dict = {p.id: p for p in products}

        if len(products_dict) < len(set(prod_ids)):
            raise NotFoundError('Uno o más productos no encontrados.')

        # 2. Validate Lines and Build Data
        validated_lines = []
        total_amount = Decimal('0.00')
        
        for line in lines_data:
            pid = int(line['product_id'])
            product = products_dict[pid]
            
            if not product.active:
                raise BusinessLogicError(f'El producto "{product.name}" no está activo.')
            
            qty = Decimal(str(line.get('qty', 0)))
            if qty <= 0:
                raise BusinessLogicError(f'Cantidad inválida para "{product.name}".')
            
            unit_cost = Decimal(str(line.get('unit_cost', 0))).quantize(Decimal('0.01'))
            if unit_cost < 0:
                raise BusinessLogicError(f'Costo negativo para "{product.name}".')
            
            line_total = (qty * unit_cost).quantize(Decimal('0.01'))
            
            validated_lines.append({
                'product_id': pid,
                'product': product,
                'qty': qty,
                'unit_cost': unit_cost,
                'line_total': line_total
            })
            total_amount += line_total

        # 3. Duplicate Prevention (Supplier + Invoice No)
        existing = session.query(PurchaseInvoice).filter(
            PurchaseInvoice.tenant_id == tenant_id,
            PurchaseInvoice.supplier_id == supplier_id,
            PurchaseInvoice.invoice_number == invoice_number
        ).first()
        if existing:
            raise BusinessLogicError(f'Factura #{invoice_number} ya existe para este proveedor.')

        # 4. Create Invoice
        invoice = PurchaseInvoice(
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=payload.get('due_date'),
            total_amount=total_amount.quantize(Decimal('0.01')),
            status=InvoiceStatus.PENDING
        )
        session.add(invoice)
        session.flush()

        # 5. Stock Movement and Invoice Lines
        stock_move = StockMove(
            tenant_id=tenant_id, date=datetime.now(), type=StockMoveType.IN,
            reference_type=StockReferenceType.INVOICE, reference_id=invoice.id,
            notes=f'Compra - Boleta #{invoice_number}'
        )
        session.add(stock_move)
        session.flush()

        for l in validated_lines:
            # Invoice Line
            session.add(PurchaseInvoiceLine(
                invoice_id=invoice.id, product_id=l['product_id'],
                qty=l['qty'], unit_cost=l['unit_cost'], line_total=l['line_total']
            ))
            
            # Update product cost
            l['product'].cost = l['unit_cost']
            
            # Stock line
            session.add(StockMoveLine(
                stock_move_id=stock_move.id, product_id=l['product_id'],
                qty=l['qty'], uom_id=l['product'].uom_id, unit_cost=l['unit_cost']
            ))

        session.commit()
        return invoice.id
        
    except (BusinessLogicError, NotFoundError) as e:
        session.rollback()
        raise e
    except Exception:
        session.rollback()
        raise
