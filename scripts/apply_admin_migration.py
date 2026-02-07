
import os
import sys
import psycopg2
from dotenv import load_dotenv

def apply_migration(migration_file):
    load_dotenv()
    
    # Use DB_HOST from env, default to localhost
    host = os.getenv('DB_HOST', 'localhost')
    # Removed the check that forced localhost if host=='db' to allow running inside docker
        
    try:
        conn = psycopg2.connect(
            host=host,
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'stock'),
            user=os.getenv('DB_USER', 'stock'),
            password=os.getenv('DB_PASSWORD', 'stock')
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print(f"Applying migration: {migration_file}")
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
            
        cur.execute(sql)
        print("Migration applied successfully!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error applying migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_admin_migration.py <path_to_sql_file>")
        sys.exit(1)
        
    migration_path = sys.argv[1]
    apply_migration(migration_path)
