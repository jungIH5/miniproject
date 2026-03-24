import os, pprint
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    row = conn.execute(text("SELECT * FROM tb_sk_diagnosis ORDER BY created_at DESC LIMIT 1")).fetchone()
    if row:
        pprint.pprint(dict(row._mapping))
    else:
        print("No row found.")
