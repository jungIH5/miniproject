from flask import Flask
from .config import Config
from .db import init_db

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # DB 초기설정
    init_db(app)

    # 블루프린트 등록 (기능별 분리 - 팀원 간 충돌 방지)
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.chat import chat_bp
    from .api import api_blueprint

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(api_blueprint)

    return app
