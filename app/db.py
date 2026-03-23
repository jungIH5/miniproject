from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def init_db(app: Flask) -> None:
    engine = create_engine(
        app.config["SQLALCHEMY_DATABASE_URI"],
        pool_pre_ping=True,
        future=True,
    )
    app.extensions["db_engine"] = engine
    
    # 서버 실행 시 DB 연결 종류를 판별하여 호환되는 문법으로 테이블 자동 생성 보장
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    is_postgres = "postgres" in uri.lower()

    try:
        with engine.begin() as conn:
            if is_postgres:
                # ---------------- PostgreSQL (Supabase) ---------------- #
                # 팀장님 요청 반영: 기존 사용 안하는 sample_items, diagnosis_results 테이블 생성 로직 제거 완료
                # [고도화] 상품 클릭 로그 테이블 추가
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS product_click_logs (
                        id BIGSERIAL PRIMARY KEY,
                        user_id VARCHAR(50),
                        product_name TEXT NOT NULL,
                        product_link TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))

                print("[DB] PostgreSQL (Supabase) 테이블 확인 및 준비 완료")
            else:
                # ---------------- MySQL ---------------- #
                # ทีม장님 요청 반영: 기존 사용 안하는 sample_items, diagnosis_results 테이블 생성 로직 제거 완료
                # [고도화] 상품 클릭 로그 테이블 추가
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS product_click_logs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(50),
                        product_name TEXT NOT NULL,
                        product_link TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_created_at (created_at)
                    );
                """))

                print("[DB] MySQL 테이블 확인 및 준비 완료")
    except SQLAlchemyError as e:
        print(f"[DB Error] 테이블 자동 생성 실패 (연결 문제 등): {e}")

    @app.get("/health")
    def healthcheck():
        try:
            with app.extensions["db_engine"].connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ok", "database": "connected"}, 200
        except SQLAlchemyError:
            return {"status": "degraded", "database": "disconnected"}, 503
