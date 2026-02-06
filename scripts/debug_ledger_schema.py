import sys
import os

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_session
from sqlalchemy import text

def inspect_schema():
    session = get_session()
    print("--- Inspecting finance_ledger columns ---")
    try:
        result = session.execute(text("SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name = 'finance_ledger'"))
        columns = [row[0] for row in result]
        for row in result:
            print(f"Column: {row[0]}, Type: {row[1]}, Default: {row[2]}")
        
        if 'payment_method' in columns:
            print("✅ 'payment_method' column EXISTS.")
        else:
            print("❌ 'payment_method' column MISSING.")
            
    except Exception as e:
        print(f"Error checking columns: {e}")

    print("\n--- Inspecting ledger_ref_type enum ---")
    try:
        # Postgres specific query to get enum values
        result = session.execute(text("SELECT unnest(enum_range(NULL::ledger_ref_type))"))
        enums = [row[0] for row in result]
        print(f"Enum values: {enums}")
        
        if 'MANUAL' in enums:
            print("✅ 'MANUAL' is in ledger_ref_type.")
        else:
            print("❌ 'MANUAL' is MISSING from ledger_ref_type.")
            
    except Exception as e:
        print(f"Error checking enum: {e}")

if __name__ == "__main__":
    inspect_schema()
