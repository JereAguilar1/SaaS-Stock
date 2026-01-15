"""Invoice service with transactional logic - Multi-Tenant."""
from decimal import Decimal
import decimal
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.models import (
    Product, Supplier, PurchaseInvoice, PurchaseInvoiceLine,
    StockMove, StockMoveLine,
    InvoiceStatus, StockMoveType, StockReferenceType
)


def create_invoice_with_lines(payload: dict, session) -> int:
    """
    Create purchase invoice with lines and update stock (tenant-scoped).
    
    Steps:
    1. Validate supplier and data (tenant-scoped)
    2. Validate lines (products must belong to tenant)
    3. Calculate totals
    4. Create purchase_invoice + purchase_invoice_line
    5. Create stock_move (IN) + stock_move_line
    6. Trigger updates product_stock
    7. Commit transaction
    
    Args:
        payload: Dictionary with:
            - tenant_id: int (REQUIRED)
            - supplier_id: int
            - invoice_number: str
            - invoice_date: date
            - due_date: date | None
            - lines: list of {product_id, qty, unit_cost}
        session: SQLAlchemy session
    
    Returns:
        invoice_id: ID of created invoice
        
    Raises:
        ValueError: For business logic errors
        Exception: For other errors
    """
    
    try:
        # Start transaction
        session.begin_nested()
        
        # Step 0: Get tenant_id
        tenant_id = payload.get('tenant_id')
        if not tenant_id:
            raise ValueError('tenant_id es requerido')
        
        # Step 1: Validate supplier belongs to tenant
        supplier_id = payload.get('supplier_id')
        if not supplier_id:
            raise ValueError('El proveedor es requerido')
        
        supplier = session.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.tenant_id == tenant_id
        ).first()
        
        if not supplier:
            raise ValueError(f'Proveedor con ID {supplier_id} no encontrado o no pertenece a su negocio')
        
        # Validate invoice data
        invoice_number = payload.get('invoice_number', '').strip()
        if not invoice_number:
            raise ValueError('El número de boleta es requerido')
        
        invoice_date = payload.get('invoice_date')
        if not invoice_date:
            raise ValueError('La fecha de boleta es requerida')
        
        due_date = payload.get('due_date')
        
        # Step 2: Validate lines (products must belong to tenant)
        lines = payload.get('lines', [])
        
        if not lines or len(lines) == 0:
            raise ValueError('Debe agregar al menos un ítem a la boleta')
        
        # Validate and prepare lines
        validated_lines = []
        total_amount = Decimal('0.00')
        
        for line in lines:
            product_id = line.get('product_id')
            if not product_id:
                raise ValueError('Producto ID es requerido en cada línea')
            
            # Get product and validate it belongs to tenant
            product = session.query(Product).filter(
                Product.id == product_id,
                Product.tenant_id == tenant_id
            ).first()
            
            if not product:
                raise ValueError(f'Producto con ID {product_id} no encontrado o no pertenece a su negocio')
            
            if not product.active:
                raise ValueError(f'El producto "{product.name}" no está activo')
            
            # Validate qty and unit_cost
            try:
                qty = Decimal(str(line.get('qty', 0)))
                if qty <= 0:
                    raise ValueError(f'La cantidad debe ser mayor a 0 para "{product.name}"')
            except (TypeError, ValueError, decimal.InvalidOperation):
                raise ValueError(f'Cantidad inválida para "{product.name}"')
            
            try:
                raw_unit_cost = Decimal(str(line.get('unit_cost', 0)))
                if raw_unit_cost < 0:
                    raise ValueError(f'El costo unitario no puede ser negativo para "{product.name}"')
                
                # Validate unit_cost is integer (no decimals)
                unit_cost = raw_unit_cost.quantize(Decimal('0.01'))
                if raw_unit_cost != unit_cost:
                    raise ValueError(f'El costo unitario debe tener exactamente 2 decimales para "{product.name}"')
                    
            except (TypeError, ValueError, decimal.InvalidOperation):
                raise ValueError(f'Costo unitario inválido para "{product.name}"')
            
            # Calculate line total
            line_total = (qty * unit_cost).quantize(Decimal('0.01'))
            
            validated_lines.append({
                'product_id': product_id,
                'product': product,
                'qty': qty,
                'unit_cost': unit_cost,
                'line_total': line_total
            })
            
            total_amount += line_total
        
        total_amount = total_amount.quantize(Decimal('0.01'))
        
        # Step 3: Check for duplicate invoice_number for same supplier (within tenant)
        existing = (session.query(PurchaseInvoice)
                   .filter(
                       PurchaseInvoice.tenant_id == tenant_id,
                       PurchaseInvoice.supplier_id == supplier_id,
                       PurchaseInvoice.invoice_number == invoice_number
                   )
                   .first())
        if existing:
            raise ValueError(
                f'Ya existe una boleta con número "{invoice_number}" '
                f'para el proveedor "{supplier.name}"'
            )
        
        # Step 4: Create PurchaseInvoice with tenant_id
        invoice = PurchaseInvoice(
            tenant_id=tenant_id,  # CRITICAL
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            total_amount=total_amount,
            status=InvoiceStatus.PENDING,
            paid_at=None
        )
        session.add(invoice)
        session.flush()  # Get invoice.id
        
        # Step 5: Create PurchaseInvoiceLines (no tenant_id)
        for line_data in validated_lines:
            invoice_line = PurchaseInvoiceLine(
                invoice_id=invoice.id,
                product_id=line_data['product_id'],
                qty=line_data['qty'],
                unit_cost=line_data['unit_cost'],
                line_total=line_data['line_total']
            )
            session.add(invoice_line)
        
        # Step 6: Create StockMove (IN) with tenant_id
        stock_move = StockMove(
            tenant_id=tenant_id,  # CRITICAL
            date=datetime.now(),
            type=StockMoveType.IN,
            reference_type=StockReferenceType.INVOICE,
            reference_id=invoice.id,
            notes=f'Compra - Boleta #{invoice_number}'
        )
        session.add(stock_move)
        session.flush()  # Get stock_move.id
        
        # Step 7: Create StockMoveLines (no tenant_id, parent is StockMove)
        # Trigger on stock_move_line will update product_stock automatically
        for line_data in validated_lines:
            product = line_data['product']
            stock_move_line = StockMoveLine(
                stock_move_id=stock_move.id,
                product_id=line_data['product_id'],
                qty=line_data['qty'],
                uom_id=product.uom_id,
                unit_cost=line_data['unit_cost']
            )
            session.add(stock_move_line)
        
        # Commit transaction
        session.commit()
        
        return invoice.id
        
    except ValueError:
        # Business logic errors - rollback and re-raise
        session.rollback()
        raise
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        
        if 'unique' in error_msg.lower() and 'invoice_number' in error_msg.lower():
            raise ValueError(
                f'Ya existe una boleta con número "{invoice_number}" '
                f'para este proveedor en su negocio'
            )
        else:
            raise Exception(f'Error de integridad: {error_msg}')
        
    except Exception as e:
        # Other errors - rollback and re-raise
        session.rollback()
        raise Exception(f'Error al crear boleta: {str(e)}')
