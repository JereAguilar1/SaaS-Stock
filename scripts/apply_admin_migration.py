
import os
import psycopg2
from dotenv import load_dotenv

def apply_migration():
    load_dotenv()
    
    # Try localhost first if db host is 'db' (container)
    host = os.getenv('DB_HOST', 'localhost')
    if host == 'db':
        host = 'localhost'
        
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
        
        migration_path = r'c:\jere\proyectos\SaaS-Stock\db\migrations\ADMIN_PANEL_V1.sql'
        print(f"Applying migration: {migration_path}")
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql = f.read()
            
        # SQL contains multiple statements, but psycopg2 can handle them if they are simple
        # However, it's better to execute it as one block if it has BEGIN/COMMIT
        cur.execute(sql)
        print("Migration applied successfully!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error applying migration: {e}")

if __name__ == "__main__":
    apply_migration()
