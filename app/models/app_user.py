"""AppUser model - platform users with email/password authentication."""
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import Base


class AppUser(Base):
    """AppUser model - platform users."""
    
    __tablename__ = 'app_user'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_tenants = relationship('UserTenant', back_populates='user')
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password, method='scrypt')
    
    def check_password(self, password):
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f"<AppUser(id={self.id}, email='{self.email}')>"
