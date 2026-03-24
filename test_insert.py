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
        conn.execute(text("INSERT INTO tb_cb_chatbot (mbr_id, sender_type, content) VALUES (1, 'user', 'test message')"))
        print("Insert successful!")
except Exception as e:
    print(f"Insert Failed: {e}")
