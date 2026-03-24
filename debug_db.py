from sqlalchemy import text
from app import create_app

def list_tables_and_columns():
    app = create_app()
    with app.extensions['db_engine'].connect() as conn:
        # Get tables
        tables_res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [r[0] for r in tables_res]
        print(f"Tables: {tables}")
        
        for table in tables:
            print(f"\nTable: {table}")
            cols_res = conn.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' AND table_schema = 'public'"))
            for col in cols_res:
                print(f" - {col[0]} ({col[1]})")

if __name__ == "__main__":
    list_tables_and_columns()
