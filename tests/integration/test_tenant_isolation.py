"""
Critical integration tests for tenant isolation.
These tests ensure that data is properly isolated between tenants.
"""

import pytest
from app.models import Product, Sale, SaleLine, FinanceLedger, Quote, PurchaseInvoice, LedgerType, SaleStatus
from app.services.dashboard_service import get_dashboard_data, get_today_datetime_range


class TestProductIsolation:
    """Test product isolation between tenants."""
    
    def test_tenant1_cannot_see_tenant2_products(self, session, product_tenant1, product_tenant2):
        """Test that tenant1 cannot see tenant2's products."""
        # Query products for tenant1
        tenant1_products = session.query(Product).filter(
            Product.tenant_id == product_tenant1.tenant_id
        ).all()
        
        # Should only see tenant1's product
        assert len(tenant1_products) == 1
        assert tenant1_products[0].id == product_tenant1.id
        assert all(p.tenant_id == product_tenant1.tenant_id for p in tenant1_products)
    
    def test_products_with_same_sku_different_tenants(self, session, tenant1, tenant2, uom):
        """Test that different tenants can have products with the same SKU."""
        # Create products with same SKU in different tenants
        product1 = Product(
            tenant_id=tenant1.id,
            name='Product A',
            sku='SHARED-SKU',
            uom_id=uom.id,
            sale_price=100,
            active=True
        )
        product2 = Product(
            tenant_id=tenant2.id,
            name='Product B',
            sku='SHARED-SKU',
            uom_id=uom.id,
            sale_price=200,
            active=True
        )
        
        session.add_all([product1, product2])
        session.commit()
        
        # Both should exist with same SKU
        assert product1.sku == product2.sku
        assert product1.tenant_id != product2.tenant_id
        
        # Query by SKU should be tenant-scoped
        tenant1_product = session.query(Product).filter(
            Product.tenant_id == tenant1.id,
            Product.sku == 'SHARED-SKU'
        ).first()
        
        assert tenant1_product.id == product1.id
        assert tenant1_product.sale_price == 100


class TestSaleIsolation:
    """Test sale isolation between tenants."""
    
    def test_tenant_sales_are_isolated(self, session, tenant1, tenant2):
        """Test that sales are isolated by tenant."""
        # Create sales for both tenants
        sale1 = Sale(
            tenant_id=tenant1.id,
            total=100.00,
            status=SaleStatus.CONFIRMED
        )
        sale2 = Sale(
            tenant_id=tenant2.id,
            total=200.00,
            status=SaleStatus.CONFIRMED
        )
        
        session.add_all([sale1, sale2])
        session.commit()
        
        # Query sales for tenant1
        tenant1_sales = session.query(Sale).filter(
            Sale.tenant_id == tenant1.id
        ).all()
        
        assert len(tenant1_sales) == 1
        assert tenant1_sales[0].id == sale1.id
        assert tenant1_sales[0].total == 100.00
        
        # Query sales for tenant2
        tenant2_sales = session.query(Sale).filter(
            Sale.tenant_id == tenant2.id
        ).all()
        
        assert len(tenant2_sales) == 1
        assert tenant2_sales[0].id == sale2.id
        assert tenant2_sales[0].total == 200.00


class TestFinanceLedgerIsolation:
    """Test finance ledger isolation between tenants."""
    
    def test_ledger_entries_are_isolated(self, session, tenant1, tenant2):
        """Test that finance ledger entries are isolated by tenant."""
        from datetime import datetime
        
        # Create ledger entries for both tenants
        ledger1 = FinanceLedger(
            tenant_id=tenant1.id,
            datetime=datetime.now(),
            type=LedgerType.INCOME,
            amount=500.00,
            category='Venta',
            reference_type='SALE',
            reference_id=1
        )
        ledger2 = FinanceLedger(
            tenant_id=tenant2.id,
            datetime=datetime.now(),
            type=LedgerType.INCOME,
            amount=1000.00,
            category='Venta',
            reference_type='SALE',
            reference_id=2
        )
        
        session.add_all([ledger1, ledger2])
        session.commit()
        
        # Query ledger for tenant1
        tenant1_ledger = session.query(FinanceLedger).filter(
            FinanceLedger.tenant_id == tenant1.id
        ).all()
        
        assert len(tenant1_ledger) == 1
        assert tenant1_ledger[0].amount == 500.00
        
        # Query ledger for tenant2
        tenant2_ledger = session.query(FinanceLedger).filter(
            FinanceLedger.tenant_id == tenant2.id
        ).all()
        
        assert len(tenant2_ledger) == 1
        assert tenant2_ledger[0].amount == 1000.00


class TestDashboardIsolation:
    """Test dashboard service respects tenant isolation."""
    
    def test_dashboard_data_is_tenant_scoped(self, session, tenant1, tenant2):
        """Test that dashboard data is properly scoped by tenant."""
        from datetime import datetime
        
        # Create sales and ledger entries for both tenants
        # Tenant 1: $500 income
        ledger_t1 = FinanceLedger(
            tenant_id=tenant1.id,
            datetime=datetime.now(),
            type=LedgerType.INCOME,
            amount=500.00,
            category='Venta',
            reference_type='SALE',
            reference_id=1
        )
        
        # Tenant 2: $1000 income
        ledger_t2 = FinanceLedger(
            tenant_id=tenant2.id,
            datetime=datetime.now(),
            type=LedgerType.INCOME,
            amount=1000.00,
            category='Venta',
            reference_type='SALE',
            reference_id=2
        )
        
        session.add_all([ledger_t1, ledger_t2])
        session.commit()
        
        # Get dashboard data for tenant1
        start_dt, end_dt = get_today_datetime_range()
        data_t1 = get_dashboard_data(session, tenant1.id, start_dt, end_dt)
        
        assert data_t1['income_today'] == 500.00
        assert data_t1['expense_today'] == 0.00
        assert data_t1['balance_today'] == 500.00
        
        # Get dashboard data for tenant2
        data_t2 = get_dashboard_data(session, tenant2.id, start_dt, end_dt)
        
        assert data_t2['income_today'] == 1000.00
        assert data_t2['expense_today'] == 0.00
        assert data_t2['balance_today'] == 1000.00
        
        # Verify no cross-tenant data leakage
        assert data_t1['income_today'] != data_t2['income_today']


class TestCrossT TenantAccessPrevention:
    """Test that cross-tenant access is prevented."""
    
    def test_accessing_other_tenant_product_by_id_fails(self, session, product_tenant1, product_tenant2):
        """Test that accessing another tenant's product by ID returns nothing when filtered by tenant."""
        # Try to access tenant2's product with tenant1's filter
        product = session.query(Product).filter(
            Product.id == product_tenant2.id,
            Product.tenant_id == product_tenant1.tenant_id  # Wrong tenant
        ).first()
        
        # Should not find the product
        assert product is None
    
    def test_bulk_queries_respect_tenant_filter(self, session, tenant1, tenant2, uom):
        """Test that bulk queries always respect tenant filter."""
        # Create multiple products for each tenant
        for i in range(5):
            product_t1 = Product(
                tenant_id=tenant1.id,
                name=f'Product T1-{i}',
                sku=f'SKU-T1-{i}',
                uom_id=uom.id,
                sale_price=100.00,
                active=True
            )
            product_t2 = Product(
                tenant_id=tenant2.id,
                name=f'Product T2-{i}',
                sku=f'SKU-T2-{i}',
                uom_id=uom.id,
                sale_price=200.00,
                active=True
            )
            session.add_all([product_t1, product_t2])
        
        session.commit()
        
        # Query products for tenant1
        tenant1_products = session.query(Product).filter(
            Product.tenant_id == tenant1.id
        ).all()
        
        # Should have exactly 5 products (plus fixture product if exists)
        assert all(p.tenant_id == tenant1.id for p in tenant1_products)
        assert not any(p.tenant_id == tenant2.id for p in tenant1_products)
