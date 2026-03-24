import os
from sqlalchemy import create_engine, text

url = os.environ.get('DATABASE_URL')
if not url:
    from dotenv import load_dotenv
    load_dotenv('c:/Users/804/Documents/pro/miniproject/.env')
    url = os.environ.get('DATABASE_URL')

engine = create_engine(url)

try:
    with engine.begin() as conn:
        res = conn.execute(text("SELECT * FROM product_click_logs")).fetchall()
        print(f"Total Rows: {len(res)}")
        for i, row in enumerate(res[:10]):
            print(f"[{i}]: {row}")
except Exception as e:
    print(f"Error: {e}")
