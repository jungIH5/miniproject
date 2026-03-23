"""AI 뷰티 상담 API 엔드포인트

POST /api/chat

[개선] ai_analyzer.chat() 통합 모듈을 통해 호출하도록 변경
"""

from flask import request, current_app, session
from sqlalchemy import text

from . import api_blueprint
from ..services import ai_analyzer


@api_blueprint.post("/chat")
def handle_chat():
    """Gemini를 활용한 AI 뷰티 상담 API + 상담기록 저장"""
    if "user_id" not in session:
        return {"success": False, "error": "로그인이 필요합니다."}, 401

    data = request.json
    if not data:
        return {"success": False, "error": "잘못된 요청입니다."}, 400

    message = data.get("message", "")
    context = data.get("context", "컨텍스트 정보가 없습니다.")
    history = data.get("history", [])

    # [개선] ai_analyzer.chat()으로 통합 호출
    result = ai_analyzer.chat(message, context, history)

    if not result.get("success"):
        return result, 500

    # ── 상담 내역 DB 저장 ──
    try:
        engine = current_app.extensions.get("db_engine")
        if engine:
            with engine.begin() as conn:
                mbr_id = int(session["user_id"])
                ai_response = result.get("response", "")
                
                # 사용자 메시지 저장
                conn.execute(
                    text("INSERT INTO tb_cb_chatbot (mbr_id, sender_type, content) VALUES (:mbr_id, 'user', :content)"),
                    {"mbr_id": mbr_id, "content": message}
                )
                
                # AI 응답 저장
                conn.execute(
                    text("INSERT INTO tb_cb_chatbot (mbr_id, sender_type, content) VALUES (:mbr_id, 'ai', :content)"),
                    {"mbr_id": mbr_id, "content": ai_response}
                )
    except Exception as e:
        current_app.logger.error(f"Chatbot DB Save Error: {e}")

    return result
