import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Schema of diagnosis_results:")
    res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='diagnosis_results'"))
    for row in res:
        print(f" - {row[0]}: {row[1]}")
