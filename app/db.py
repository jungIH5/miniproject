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
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS sample_items (
                        id BIGSERIAL PRIMARY KEY,
                        title VARCHAR(120) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS diagnosis_results (
                        id BIGSERIAL PRIMARY KEY,
                        session_id VARCHAR(36) NOT NULL,
                        personal_color_season VARCHAR(30),
                        skin_type VARCHAR(30),
                        overall_score INT DEFAULT 0,
                        analysis_method VARCHAR(30) DEFAULT 'basic',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_session_id ON diagnosis_results(session_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_created_at ON diagnosis_results(created_at);"))
                print("[DB] PostgreSQL (Supabase) 테이블 확인 및 준비 완료")
            else:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS sample_items (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(120) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS diagnosis_results (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(36) NOT NULL,
                        personal_color_season VARCHAR(30),
                        skin_type VARCHAR(30),
                        overall_score INT DEFAULT 0,
                        analysis_method VARCHAR(30) DEFAULT 'basic',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_session_id (session_id),
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
