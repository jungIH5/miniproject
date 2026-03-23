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
        res = conn.execute(text("SELECT * FROM tb_cb_chatbot LIMIT 5")).fetchall()
        print(f"tb_cb_chatbot row count retrieved: {len(res)}")
        for r in res:
            print(r)
except Exception as e:
    print(f"Failed: {e}")
