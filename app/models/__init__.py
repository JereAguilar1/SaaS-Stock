"""Models package - exports all SQLAlchemy models."""
# SaaS Core Models
from app.models.admin_user import AdminUser
from app.models.app_user import AppUser
from app.models.tenant import Tenant
from app.models.user_tenant import UserTenant, UserRole

# Business Models
from app.models.uom import UOM
from app.models.category import Category
from app.models.product import Product
from app.models.product_feature import ProductFeature
from app.models.product_stock import ProductStock
from app.models.sale import Sale, SaleStatus
from app.models.sale_line import SaleLine
from app.models.sale_draft import SaleDraft
from app.models.sale_draft_line import SaleDraftLine
from app.models.sale_payment import SalePayment
from app.models.stock_move import StockMove, StockMoveType, StockReferenceType
from app.models.stock_move_line import StockMoveLine
from app.models.finance_ledger import FinanceLedger, LedgerType, LedgerReferenceType, PaymentMethod, normalize_payment_method
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.purchase_invoice import PurchaseInvoice, InvoiceStatus
from app.models.purchase_invoice_payment import PurchaseInvoicePayment
from app.models.purchase_invoice_line import PurchaseInvoiceLine
from app.models.quote import Quote, QuoteStatus
from app.models.quote_line import QuoteLine
from app.models.missing_product_request import MissingProductRequest, normalize_missing_product_name
from app.models.audit_log import AuditLog, AuditAction  # PASO 6

# Admin Panel V2
from app.models.subscription import Subscription, Payment
from app.models.admin_audit import AdminAuditLog, AuditAction as AdminAuditAction

__all__ = [
    # SaaS Core
    'Tenant', 'AppUser', 'UserTenant', 'UserRole',
    # Business
    'UOM', 'Category', 'Product', 'ProductFeature', 'ProductStock',
    'Sale', 'SaleStatus', 'SaleLine', 'SaleDraft', 'SaleDraftLine', 'SalePayment',
    'StockMove', 'StockMoveType', 'StockReferenceType', 'StockMoveLine',
    'FinanceLedger', 'LedgerType', 'LedgerReferenceType', 'PaymentMethod', 'normalize_payment_method',
    'Supplier', 'Customer', 'PurchaseInvoice', 'InvoiceStatus', 'PurchaseInvoicePayment', 'PurchaseInvoiceLine',
    'Quote', 'QuoteStatus', 'QuoteLine',
    'MissingProductRequest', 'normalize_missing_product_name',
    'AuditLog', 'AuditAction',  # PASO 6
    # Admin Panel V2
    'AdminUser', 'Subscription', 'Payment', 'AdminAuditLog', 'AdminAuditAction',
]

