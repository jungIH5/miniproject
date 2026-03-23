import os
from sqlalchemy import create_engine, text

url = os.environ.get('DATABASE_URL')
if not url:
    from dotenv import load_dotenv
    load_dotenv('c:/Users/804/Documents/pro/miniproject/.env')
    url = os.environ.get('DATABASE_URL')

engine = create_engine(url)

with engine.begin() as conn:
    # 1. tb_cs_members -> tb_cs_member
    try:
        members_data = conn.execute(text("SELECT mbr_id, mbr_name, mbr_pwd, mbr_email, mbr_status, created_at FROM tb_cs_members")).fetchall()
        print(f"Migrating {len(members_data)} rows from tb_cs_members to tb_cs_member...")
        
        for row in members_data:
            # Check if user already exists
            exists = conn.execute(text("SELECT 1 FROM tb_cs_member WHERE mbr_name = :name"), {"name": row[1]}).fetchone()
            if not exists:
                conn.execute(
                    text("INSERT INTO tb_cs_member (mbr_name, mbr_pwd, mbr_email, mbr_status, created_at) VALUES (:name, :pwd, :email, :status, :created_at)"),
                    {"name": row[1], "pwd": row[2], "email": row[3], "status": row[4], "created_at": row[5]}
                )
        conn.execute(text("DROP TABLE IF EXISTS tb_cs_members"))
        print("Dropped tb_cs_members")
    except Exception as e:
        print(f"Error migrating members: {e}")

    # 2. diagnosis_results -> tb_sk_diagnosis
    try:
        conn.execute(text("ALTER TABLE tb_sk_diagnosis ALTER COLUMN mbr_id DROP NOT NULL"))
        
        diag_data = conn.execute(text("SELECT id, session_id, personal_color_season, skin_type, overall_score, analysis_method, created_at FROM diagnosis_results")).fetchall()
        print(f"Migrating {len(diag_data)} rows from diagnosis_results to tb_sk_diagnosis...")
        
        for row in diag_data:
            conn.execute(
                text("""
                    INSERT INTO tb_sk_diagnosis (
                        color, type, type_score, color_rmk, created_at
                    ) VALUES (
                        :color, :type, :type_score, :method, :created_at
                    )
                """),
                {
                    "color": row[2], 
                    "type": row[3], 
                    "type_score": row[4], 
                    "method": "Migrated from " + str(row[5]),
                    "created_at": row[6]
                }
            )
        conn.execute(text("DROP TABLE IF EXISTS diagnosis_results"))
        print("Dropped diagnosis_results")
    except Exception as e:
        print(f"Error migrating diagnosis: {e}")

print("Migration complete!")
