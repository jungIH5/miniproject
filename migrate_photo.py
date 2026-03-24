from sqlalchemy import text
from app import create_app

def migrate():
    app = create_app()
    with app.extensions['db_engine'].begin() as conn:
        print("Checking tb_cs_member table...")
        # Check if column exists (optional, but safer)
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'tb_cs_member' AND column_name = 'mbr_photo'"))
        if not res.fetchone():
            print("Adding mbr_photo column to tb_cs_member...")
            conn.execute(text("ALTER TABLE tb_cs_member ADD COLUMN mbr_photo TEXT DEFAULT ''"))
            print("Column added successfully.")
        else:
            print("Column mbr_photo already exists.")

if __name__ == "__main__":
    migrate()
