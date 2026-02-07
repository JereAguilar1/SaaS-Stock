
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import AppUser
from app.database import get_session

def list_users():
    app = create_app()
    with app.app_context():
        session = get_session()
        users = session.query(AppUser).all()
        print(f"Found {len(users)} users:")
        for u in users:
            print(f"ID: {u.id}, Email: {u.email}, AuthProvider: {u.auth_provider}, PasswordHash: {'YES' if u.password_hash else 'NO'}, IsOAuth: {u.is_oauth_user() if hasattr(u, 'is_oauth_user') else 'N/A'}")

if __name__ == "__main__":
    list_users()
