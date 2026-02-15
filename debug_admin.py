import sys
import os

# Add app directory to path
sys.path.append(os.getcwd())

try:
    from app.blueprints.admin import admin_bp
    print("SUCCESS: blueprint admin_bp loaded.")
except Exception as e:
    import traceback
    print("FAILED to load blueprint admin_bp:")
    traceback.print_exc()
