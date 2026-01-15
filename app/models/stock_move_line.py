"""Stock Move Line model."""
from sqlalchemy import Column, BigInteger, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class StockMoveLine(Base):
    """Stock Move Line (detalle de movimiento de stock)."""
    
    __tablename__ = 'stock_move_line'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_move_id = Column(BigInteger, ForeignKey('stock_move.id'), nullable=False)
    product_id = Column(BigInteger, ForeignKey('product.id'), nullable=False)
    qty = Column(Numeric(10, 2), nullable=False)
    uom_id = Column(BigInteger, ForeignKey('uom.id'), nullable=False)
    unit_cost = Column(Numeric(10, 2), nullable=True)
    
    # Relationships
    stock_move = relationship('StockMove', back_populates='lines')
    product = relationship('Product')
    uom = relationship('UOM')
    
    def __repr__(self):
        return f"<StockMoveLine(id={self.id}, product_id={self.product_id}, qty={self.qty})>"

