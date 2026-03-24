from flask import Blueprint

# 팀원(Knockcha)의 요청으로 추가된 API 블루프린트입니다.
api_blueprint = Blueprint('api', __name__, url_prefix='/api')

from . import diagnosis
