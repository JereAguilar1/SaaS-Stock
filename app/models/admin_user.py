"""AdminUser model - global platform administrators (no tenant association)."""
from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import Base


class AdminUser(Base):
    """AdminUser model - global platform administrators.
    
    IMPORTANT: Admin users have NO tenant_id. They operate globally across all tenants.
    This is fundamentally different from AppUser (which has UserTenant relationships).
    """
    
    __tablename__ = 'admin_users'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password, method='scrypt')
    
    def check_password(self, password):
        """Check password against hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """Update last_login timestamp to current time."""
        self.last_login = func.now()
    
    def __repr__(self):
        return f"<AdminUser(id={self.id}, email='{self.email}')>"
