"""Ledger blueprint for finance ledger management - Multi-Tenant."""
from flask import Blueprint, render_template, request, flash, redirect, url_for, g, abort
from datetime import datetime, date
from decimal import Decimal
import decimal
from app.database import get_session
from app.models import FinanceLedger, LedgerType, LedgerReferenceType, PaymentMethod
from app.middleware import require_login, require_tenant

ledger_bp = Blueprint('ledger', __name__, url_prefix='/ledger')


@ledger_bp.route('/')
@require_login
@require_tenant
def list_ledger():
    """List all finance ledger entries (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get query params
        entry_type = request.args.get('type', '').upper()
        start_str = request.args.get('start', '').strip()
        end_str = request.args.get('end', '').strip()
        method = request.args.get('method', 'all').lower().strip()
        
        # Validate method
        if method not in ['all', 'cash', 'transfer', 'card', 'cuenta_corriente']:
            flash('Método de pago inválido. Mostrando todos.', 'info')
            method = 'all'
        
        # Build query - filter by tenant FIRST
        query = db_session.query(FinanceLedger).filter(
            FinanceLedger.tenant_id == g.tenant_id
        )
        
        # Filter by type
        if entry_type and entry_type in ['INCOME', 'EXPENSE', 'INVOICE']:
            query = query.filter(FinanceLedger.type == LedgerType[entry_type])
        
        # Filter by payment method
        if method == 'cash':
            query = query.filter(FinanceLedger.payment_method == 'CASH')
        elif method == 'transfer':
            query = query.filter(FinanceLedger.payment_method == 'TRANSFER')
        elif method == 'card':
            query = query.filter(FinanceLedger.payment_method == 'CARD')
        elif method == 'cuenta_corriente':
            query = query.filter(FinanceLedger.payment_method == 'CUENTA_CORRIENTE')
        
        # Filter by date range
        if start_str:
            try:
                start_dt = datetime.strptime(start_str, '%Y-%m-%d')
                query = query.filter(FinanceLedger.datetime >= start_dt)
            except ValueError:
                pass
        
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                query = query.filter(FinanceLedger.datetime <= end_dt)
            except ValueError:
                pass
        
        # Order by datetime desc
        entries = query.order_by(FinanceLedger.datetime.desc()).all()
        
        return render_template(
            'ledger/list.html',
            entries=entries,
            entry_type=entry_type,
            selected_method=method,
            start=start_str,
            end=end_str
        )
        
    except Exception as e:
        flash(f'Error al cargar libro mayor: {str(e)}', 'danger')
        return render_template('ledger/list.html', entries=[], entry_type='', start='', end='')


@ledger_bp.route('/new', methods=['GET'])
@require_login
@require_tenant
def new_ledger():
    """Show form to create manual ledger entry."""
    today = date.today().strftime('%Y-%m-%d')
    now_time = datetime.now().strftime('%H:%M')
    return render_template('ledger/form.html', today=today, now_time=now_time)


@ledger_bp.route('/new', methods=['POST'])
@require_login
@require_tenant
def create_ledger():
    """Create manual ledger entry (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get form data
        raw_type = request.form.get('type', '').upper()
        amount_str = request.form.get('amount', '').strip()
        datetime_str = request.form.get('datetime', '').strip()
        category = request.form.get('category', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        payment_method = request.form.get('payment_method', 'CASH').upper()
        
        # Handle type and reference_type logic
        if raw_type == 'INVOICE':
            entry_type = 'INVOICE'
            ref_type = LedgerReferenceType.SALE  # Blue "Venta" badge
            if not category:
                category = 'Ventas'
        else:
            entry_type = raw_type
            ref_type = LedgerReferenceType.MANUAL
        
        # Validations
        if entry_type not in ['INCOME', 'EXPENSE', 'INVOICE']:
            flash('Tipo de movimiento inválido', 'danger')
            return redirect(url_for('ledger.new_ledger'))
        
        if payment_method not in ['CASH', 'TRANSFER', 'CARD', 'CUENTA_CORRIENTE']:
            flash('Método de pago inválido', 'danger')
            return redirect(url_for('ledger.new_ledger'))
        
        if not amount_str:
            flash('El monto es requerido', 'danger')
            return redirect(url_for('ledger.new_ledger'))
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                flash('El monto debe ser mayor a 0', 'danger')
                return redirect(url_for('ledger.new_ledger'))
        except (ValueError, decimal.InvalidOperation):
            flash('Monto inválido', 'danger')
            return redirect(url_for('ledger.new_ledger'))
        
        # Parse datetime
        if datetime_str:
            try:
                entry_datetime = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Formato de fecha/hora inválido', 'danger')
                return redirect(url_for('ledger.new_ledger'))
        else:
            entry_datetime = datetime.now()
        
        # Create ledger entry with tenant_id
        from app.models import normalize_payment_method
        payment_method_normalized = normalize_payment_method(payment_method)
        
        ledger = FinanceLedger(
            tenant_id=g.tenant_id,  # CRITICAL
            datetime=entry_datetime,
            type=LedgerType[entry_type],
            amount=amount,
            reference_type=ref_type,
            reference_id=None,
            category=category,
            notes=notes,
            payment_method=payment_method_normalized
        )
        
        db_session.add(ledger)
        db_session.commit()
        
        method_labels = {
            'CASH': 'Efectivo',
            'TRANSFER': 'Transferencia',
            'CARD': 'Tarjeta',
            'CUENTA_CORRIENTE': 'Cuenta Corriente'
        }
        payment_label = method_labels.get(payment_method, payment_method)
        flash(f'Movimiento manual de tipo {entry_type} por ${amount} ({payment_label}) registrado exitosamente', 'success')
        return redirect(url_for('ledger.list_ledger'))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al crear movimiento: {str(e)}', 'danger')
        return redirect(url_for('ledger.new_ledger'))
