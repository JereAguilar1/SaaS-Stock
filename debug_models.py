import sys
import os

# Asegurar que el directorio actual estÃ© en el path
sys.path.append(os.getcwd())

from app.database import Base
# Importar app.models para forzar el registro
try:
    import app.models
    print("SUCCESS: app.models imported")
except Exception as e:
    print(f"ERROR: Failed to import app.models: {e}")

print(f"Tables registered in Base.metadata ({len(Base.metadata.tables)} total):")
sorted_tables = sorted(list(Base.metadata.tables.keys()))
for table_name in sorted_tables:
    print(f"- {table_name}")

# Verificar especÃ­ficamente los problematicos
problematic = ['admin_users', 'admin_audit_logs', 'audit_log']
print("\nChecking problematic tables:")
for t in problematic:
    if t in Base.metadata.tables:
        print(f"[OK] {t} is registered")
    else:
        print(f"[FAIL] {t} is NOT registered")
