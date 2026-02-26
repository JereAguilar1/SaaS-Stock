"""Product model."""
from sqlalchemy import Column, BigInteger, String, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Product(Base):
    """Product model."""
    
    __tablename__ = 'product'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    sku = Column(String, nullable=True)
    barcode = Column(String, nullable=True)
    name = Column(String, nullable=False)
    category_id = Column(BigInteger, ForeignKey('category.id'), nullable=True)
    uom_id = Column(BigInteger, ForeignKey('uom.id'), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    is_unlimited_stock = Column(Boolean, nullable=False, default=False, server_default='false')
    sale_price = Column(Numeric(10, 2), nullable=False)
    cost = Column(Numeric(10, 2), nullable=False, default=0, server_default='0.00')  # Precio de compra
    image_path = Column(String(255), nullable=True)
    image_original_path = Column(String(255), nullable=True)
    min_stock_qty = Column(BigInteger, nullable=False, default=0, server_default='0')  # MEJORA 11 - Changed to INTEGER
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship('Tenant')
    category = relationship('Category', foreign_keys=[category_id])
    uom = relationship('UOM', foreign_keys=[uom_id])
    # Cascade delete-orphan: Al eliminar el producto, se elimina automáticamente su stock
    stock = relationship('ProductStock', uselist=False, back_populates='product', cascade="all, delete-orphan")
    features = relationship('ProductFeature', backref='product', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', sku='{self.sku}')>"
    
    @property
    def on_hand_qty(self):
        """Get on hand quantity from stock."""
        if self.stock:
            return self.stock.on_hand_qty
        return 0

    @property
    def image_url(self):
        """
        Get dynamic public URL for product image.
        
        Handles:
        1. Legacy full URLs (starts with http) - returns as is
        2. New relative paths (object keys) - joins with S3_PUBLIC_URL
        3. No image - returns None
        """
        if not self.image_path:
            return None
            
        # If it's already a full URL (legacy), return it
        if self.image_path.startswith(('http://', 'https://')):
            return self.image_path
            
        # It's a relative object key
        from flask import current_app
        public_url = current_app.config.get('S3_PUBLIC_URL', 'http://localhost:9000')
        bucket = current_app.config.get('S3_BUCKET', 'uploads')
        
        # Ensure no double slashes when joining
        base = public_url.rstrip('/')
        collection = bucket.strip('/')
        path = self.image_path.lstrip('/')
        
        return f"{base}/{collection}/{path}"

    @property
    def image_original_url(self):
        """
        Get dynamic public URL for ORIGINAL product image.
        Uses image_original_path if available, otherwise falls back to image_url (for legacy).
        """
        target_path = self.image_original_path if self.image_original_path else self.image_path

        if not target_path:
            return None
            
        # If it's already a full URL (legacy), return it
        if target_path.startswith(('http://', 'https://')):
            return target_path
            
        # It's a relative object key
        from flask import current_app
        public_url = current_app.config.get('S3_PUBLIC_URL', 'http://localhost:9000')
        bucket = current_app.config.get('S3_BUCKET', 'uploads')
        
        # Ensure no double slashes when joining
        base = public_url.rstrip('/')
        collection = bucket.strip('/')
        path = target_path.lstrip('/')
        
        return f"{base}/{collection}/{path}"

