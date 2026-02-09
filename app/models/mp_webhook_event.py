"""Mercado Pago Webhook Event model for idempotency."""
from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class MPWebhookEvent(Base):
    """Log de eventos webhook de Mercado Pago para idempotencia."""
    __tablename__ = 'mp_webhook_event'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    topic = Column(String(50), nullable=False, index=True)
    mp_event_id = Column(String(100))
    resource_id = Column(String(100), index=True)
    payload_json = Column(JSONB, nullable=False)
    dedupe_key = Column(String(64), nullable=False, unique=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False, default='RECEIVED', index=True)
    
    def __repr__(self):
        return f"<MPWebhookEvent(topic='{self.topic}', resource_id='{self.resource_id}', status='{self.status}')>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'topic': self.topic,
            'mp_event_id': self.mp_event_id,
            'resource_id': self.resource_id,
            'payload': self.payload_json,
            'dedupe_key': self.dedupe_key,
            'received_at': self.received_at.isoformat(),
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'status': self.status
        }
    
    @property
    def is_processed(self):
        """Check if event has been processed."""
        return self.status == 'PROCESSED'
