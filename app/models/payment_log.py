from app.database import Base
from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime

class PaymentLog(Base):
    __tablename__ = 'payment_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey('sale.id'), nullable=False)
    amount = Column(Numeric(10, 2), default=0)
    date = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
