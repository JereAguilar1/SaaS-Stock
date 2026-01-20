"""
Unit tests for SQLAlchemy models.
"""

import pytest
from app.models import Tenant, AppUser, UserTenant, Product, Sale


class TestTenantModel:
    """Tests for Tenant model."""
    
    def test_create_tenant(self, session):
        """Test creating a tenant."""
        tenant = Tenant(
            slug='test-tenant',
            name='Test Tenant',
            active=True
        )
        session.add(tenant)
        session.commit()
        
        assert tenant.id is not None
        assert tenant.slug == 'test-tenant'
        assert tenant.name == 'Test Tenant'
        assert tenant.active is True
    
    def test_tenant_slug_unique(self, session, tenant1):
        """Test that tenant slug must be unique."""
        duplicate_tenant = Tenant(
            slug=tenant1.slug,
            name='Duplicate Tenant'
        )
        session.add(duplicate_tenant)
        
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


class TestAppUserModel:
    """Tests for AppUser model."""
    
    def test_create_user(self, session):
        """Test creating a user."""
        user = AppUser(
            email='test@example.com',
            full_name='Test User',
            active=True
        )
        user.set_password('securepassword')
        session.add(user)
        session.commit()
        
        assert user.id is not None
        assert user.email == 'test@example.com'
        assert user.password_hash is not None
        assert user.password_hash != 'securepassword'
    
    def test_password_hashing(self, session):
        """Test password hashing and verification."""
        user = AppUser(email='user@test.com', active=True)
        user.set_password('mypassword')
        
        assert user.check_password('mypassword') is True
        assert user.check_password('wrongpassword') is False
    
    def test_user_email_unique(self, session, user1):
        """Test that user email must be unique."""
        duplicate_user = AppUser(
            email=user1.email,
            full_name='Duplicate User'
        )
        session.add(duplicate_user)
        
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


class TestUserTenantModel:
    """Tests for UserTenant relationship model."""
    
    def test_create_user_tenant(self, session, user1, tenant1):
        """Test creating user-tenant relationship."""
        # Already created in fixture, verify it exists
        user_tenant = session.query(UserTenant).filter_by(
            user_id=user1.id,
            tenant_id=tenant1.id
        ).first()
        
        assert user_tenant is not None
        assert user_tenant.role == 'OWNER'
        assert user_tenant.active is True
    
    def test_user_can_belong_to_multiple_tenants(self, session, user1, tenant1, tenant2):
        """Test that a user can belong to multiple tenants."""
        # Add user1 to tenant2
        user_tenant2 = UserTenant(
            user_id=user1.id,
            tenant_id=tenant2.id,
            role='ADMIN',
            active=True
        )
        session.add(user_tenant2)
        session.commit()
        
        user_tenants = session.query(UserTenant).filter_by(user_id=user1.id).all()
        assert len(user_tenants) == 2
        assert any(ut.tenant_id == tenant1.id for ut in user_tenants)
        assert any(ut.tenant_id == tenant2.id for ut in user_tenants)


class TestProductModel:
    """Tests for Product model."""
    
    def test_create_product(self, session, tenant1, uom):
        """Test creating a product."""
        product = Product(
            tenant_id=tenant1.id,
            name='Test Product',
            sku='TEST-001',
            uom_id=uom.id,
            sale_price=50.00,
            min_stock_qty=5,
            active=True
        )
        session.add(product)
        session.commit()
        
        assert product.id is not None
        assert product.tenant_id == tenant1.id
        assert product.name == 'Test Product'
        assert product.sale_price == 50.00
    
    def test_product_sku_unique_per_tenant(self, session, tenant1, tenant2, uom):
        """Test that SKU must be unique within a tenant."""
        # Create product in tenant1
        product1 = Product(
            tenant_id=tenant1.id,
            name='Product 1',
            sku='UNIQUE-SKU',
            uom_id=uom.id,
            sale_price=100.00,
            active=True
        )
        session.add(product1)
        session.commit()
        
        # Same SKU in tenant2 should work
        product2 = Product(
            tenant_id=tenant2.id,
            name='Product 2',
            sku='UNIQUE-SKU',
            uom_id=uom.id,
            sale_price=200.00,
            active=True
        )
        session.add(product2)
        session.commit()
        
        assert product1.sku == product2.sku
        assert product1.tenant_id != product2.tenant_id
        
        # Same SKU in same tenant should fail
        product3 = Product(
            tenant_id=tenant1.id,
            name='Product 3',
            sku='UNIQUE-SKU',
            uom_id=uom.id,
            sale_price=300.00,
            active=True
        )
        session.add(product3)
        
        with pytest.raises(Exception):  # IntegrityError
            session.commit()
