"""Sale Payment model for mixed payment methods."""
from sqlalchemy import Column, BigInteger, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class SalePayment(Base):
    """
    Sale Payment - Individual payment for a sale.
    
    Allows mixed payment methods (e.g., CASH + TRANSFER).
    Multiple payments can be associated with a single sale.
    """
    
    __tablename__ = 'sale_payment'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sale_id = Column(BigInteger, ForeignKey('sale.id', ondelete='CASCADE'), nullable=False, index=True)
    
    payment_method = Column(String(20), nullable=False)  # CASH, TRANSFER, CARD
    amount = Column(Numeric(10, 2), nullable=False)
    
    # Only for CASH payments
    amount_received = Column(Numeric(10, 2))  # Amount given by customer
    change_amount = Column(Numeric(10, 2))    # Change returned
    
    # Relationships
    sale = relationship('Sale', back_populates='payments')
    
    def __repr__(self):
        return f"<SalePayment(id={self.id}, sale_id={self.sale_id}, method={self.payment_method}, amount={self.amount})>"
