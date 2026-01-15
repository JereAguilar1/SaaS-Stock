"""Database configuration and initialization."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base

# Create SQLAlchemy base
Base = declarative_base()

# Global session and engine
engine = None
db_session = None


def init_db(app):
    """Initialize database connection."""
    global engine, db_session
    
    database_uri = app.config['SQLALCHEMY_DATABASE_URI']
    engine = create_engine(
        database_uri,
        echo=app.config.get('SQLALCHEMY_ECHO', False),
        pool_pre_ping=True,  # Enable connection health checks
        pool_size=10,
        max_overflow=20
    )
    
    db_session = scoped_session(
        sessionmaker(autocommit=False, autoflush=False, bind=engine)
    )
    
    Base.query = db_session.query_property()
    
    # Register teardown
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Close database session and rollback on error."""
        if exception:
            db_session.rollback()
        db_session.remove()


def get_session():
    """Get database session."""
    return db_session


# Alias for easier imports
db = db_session

