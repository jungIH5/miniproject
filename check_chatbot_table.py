import os
from sqlalchemy import create_engine, inspect

url = os.environ.get('DATABASE_URL')
if not url:
    from dotenv import load_dotenv
    load_dotenv('c:/Users/804/Documents/pro/miniproject/.env')
    url = os.environ.get('DATABASE_URL')

engine = create_engine(url)
inspector = inspect(engine)

for table_name in inspector.get_table_names():
    if 'chat' in table_name.lower():
        print(f"Table: {table_name}")
        for col in inspector.get_columns(table_name):
            print(f"  - {col['name']}: {col['type']}")
