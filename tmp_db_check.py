import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Tables:")
    res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
    for row in res:
        print(f" - {row[0]}")
    
    print("\nContent of diagnosis_results:")
    try:
        res = conn.execute(text("SELECT count(*) FROM diagnosis_results"))
        print(f"Count: {res.scalar()}")
        res = conn.execute(text("SELECT * FROM diagnosis_results LIMIT 5"))
        for row in res:
            print(row)
    except Exception as e:
        print(f"Error reading diagnosis_results: {e}")
