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
        res = conn.execute(text("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid WHERE t.relname = 'tb_cb_chatbot' AND c.contype = 'c'")).fetchall()
        print("Constraint details:", res)
except Exception as e:
    print(e)
