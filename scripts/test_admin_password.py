from app.models import AdminUser
from app.database import db_session

admin = db_session.query(AdminUser).filter_by(email='tandiliatech@gmail.com').first()
print(f'Admin found: {admin}')
if admin:
    print(f'Password hash exists: {bool(admin.password_hash)}')
    print(f'Hash length: {len(admin.password_hash)}')
    test_password = 'Tandil2025'
    result = admin.check_password(test_password)
    print(f'Check password "{test_password}": {result}')
