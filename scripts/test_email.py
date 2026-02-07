
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.email_service import send_password_reset_email

def test_email():
    app = create_app()
    with app.app_context():
        print("Testing email sending...")
        print(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
        print(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
        print(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
        print(f"MAIL_SUPPRESS_SEND: {app.config.get('MAIL_SUPPRESS_SEND')}")
        
        # Test email
        to_email = "tandilaitech@gmail.com" # Send to self for testing
        link = "http://localhost:5000/reset-password/test-token"
        
        result = send_password_reset_email(to_email, link)
        print(f"Result: {result}")

if __name__ == "__main__":
    test_email()
