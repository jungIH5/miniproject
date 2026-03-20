"""AI 뷰티 상담 API 엔드포인트

POST /api/chat

[개선] ai_analyzer.chat() 통합 모듈을 통해 호출하도록 변경
"""

from flask import request

from . import api_blueprint
from ..services import ai_analyzer


@api_blueprint.post("/chat")
def handle_chat():
    """Gemini를 활용한 AI 뷰티 상담 API"""
    data = request.json
    if not data:
        return {"success": False, "error": "잘못된 요청입니다."}, 400

    message = data.get("message", "")
    context = data.get("context", "컨텍스트 정보가 없습니다.")
    history = data.get("history", [])

    # [개선] ai_analyzer.chat()으로 통합 호출
    result = ai_analyzer.chat(message, context, history)

    if not result["success"]:
        return result, 500
    return result
