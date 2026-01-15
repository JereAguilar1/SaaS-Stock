"""Stock Move model."""
from sqlalchemy import Column, BigInteger, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class StockMoveType(enum.Enum):
    """Stock move type enum."""
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"


class StockReferenceType(enum.Enum):
    """Stock move reference type enum."""
    SALE = "SALE"
    INVOICE = "INVOICE"
    MANUAL = "MANUAL"


class StockMove(Base):
    """Stock Move (movimiento de stock)."""
    
    __tablename__ = 'stock_move'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    type = Column(Enum(StockMoveType, name='stock_move_type'), nullable=False)
    reference_type = Column(Enum(StockReferenceType, name='stock_ref_type'), nullable=False)
    reference_id = Column(BigInteger, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    tenant = relationship('Tenant')
    lines = relationship('StockMoveLine', back_populates='stock_move', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<StockMove(id={self.id}, type={self.type.value}, reference_type={self.reference_type.value})>"

