import os
from sqlalchemy import create_engine, inspect

url = os.environ.get('DATABASE_URL')
if not url:
    # Use fallback from .env
    from dotenv import load_dotenv
    load_dotenv('c:/Users/804/Documents/pro/miniproject/.env')
    url = os.environ.get('DATABASE_URL')

engine = create_engine(url)
inspector = inspect(engine)

for table_name in inspector.get_table_names():
    print(f'\nTable: {table_name}')
    for column in inspector.get_columns(table_name):
        print(f'  - {column["name"]}: {column["type"]}')
