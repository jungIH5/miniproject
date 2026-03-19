import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    DB_HOST = os.getenv("DB_HOST", "db")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "app_db")
    DB_USER = os.getenv("DB_USER", "app_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "app_password")

    # .env에 DATABASE_URL 이 직접 명시되어 있으면 우선적으로 사용합니다 (Supabase 등 연결에 용이)
    default_uri = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", default_uri)

    # 기본 postgres:// 를 SQLAlchemy 최신 기준인 postgresql:// 로 자동 변환합니다.
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    # ── 외부 딥러닝 피부 분석 API (팀원 모델) ──
    SKIN_API_URL = os.getenv("SKIN_API_URL", "")
    SKIN_API_KEY = os.getenv("SKIN_API_KEY", "")
    SKIN_API_TIMEOUT = int(os.getenv("SKIN_API_TIMEOUT", "30"))

    # ── 네이버 쇼핑 API (실제 제품 추천) ──
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

    # ── 제미나이(Gemini) API ──
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # ── 업로드 설정 ──
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
