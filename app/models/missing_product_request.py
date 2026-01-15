"""Missing Product Request model for tracking customer requests for products not in the system."""
from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, CheckConstraint, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MissingProductRequest(Base):
    """
    Missing Product Request - tracks products customers ask for but we don't have.
    
    Use case: Customer asks for "Tornillo 10mm hexagonal" but we don't sell it.
    We track how many times it's requested to prioritize purchasing.
    """
    
    __tablename__ = 'missing_product_request'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)
    request_count = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default='OPEN')
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    tenant = relationship('Tenant')
    
    __table_args__ = (
        CheckConstraint('request_count >= 0', name='missing_product_request_count_check'),
        CheckConstraint("status IN ('OPEN', 'RESOLVED')", name='missing_product_request_status_check'),
    )
    
    def __repr__(self):
        return f"<MissingProductRequest(id={self.id}, name='{self.name}', count={self.request_count}, status='{self.status}')>"


def normalize_missing_product_name(name: str) -> str:
    """
    Normalize product name for deduplication.
    
    - Trim whitespace
    - Lowercase
    - Collapse multiple spaces to one
    - Remove accents (optional, but helps with variations)
    
    Examples:
        " Tornillo 8MM " -> "tornillo 8mm"
        "Cable  UTP   cat5e" -> "cable utp cat5e"
    
    Args:
        name: Original product name
        
    Returns:
        Normalized name for deduplication
    """
    if not name:
        return ""
    
    # Trim and lowercase
    normalized = name.strip().lower()
    
    # Collapse multiple spaces to one
    import re
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Optional: Remove common punctuation that doesn't add meaning
    # normalized = re.sub(r'[,.\-_()]+', ' ', normalized)
    # normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized
