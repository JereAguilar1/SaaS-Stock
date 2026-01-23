"""AppUser model - platform users with email/password or OAuth authentication."""
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import Base


class AppUser(Base):
    """AppUser model - platform users with local or OAuth authentication."""
    
    __tablename__ = 'app_user'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth users
    full_name = Column(String(200), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    
    # OAuth fields (GOOGLE_AUTH)
    google_sub = Column(String(255), nullable=True, unique=True)
    auth_provider = Column(String(20), nullable=False, default='local')
    email_verified = Column(Boolean, nullable=False, default=False)
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_tenants = relationship('UserTenant', back_populates='user')
    
    def set_password(self, password):
        """Set password hash (for local auth)."""
        self.password_hash = generate_password_hash(password, method='scrypt')
        self.auth_provider = 'local'
        self.email_verified = True  # Assume email verified after registration
    
    def check_password(self, password):
        """Check password against hash (for local auth)."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def is_oauth_user(self):
        """Check if user uses OAuth authentication."""
        return self.auth_provider != 'local'
    
    def __repr__(self):
        return f"<AppUser(id={self.id}, email='{self.email}', provider='{self.auth_provider}')>"
