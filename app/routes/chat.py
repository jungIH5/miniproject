from flask import Blueprint, request, jsonify, session, current_app
import google.generativeai as genai

chat_bp = Blueprint('chat', __name__)

@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """
    [백엔드 역할] 
    1. 분석 결과 데이터를 기반으로 프롬프트 조합
    2. 제미나이 API 호출 및 사용자와의 대화 처리
    """
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401
    
    # ── 제미나이 설정 및 대화 처리 (백엔드 관리) ──
    api_key = current_app.config["GEMINI_API_KEY"]
    # ... (생략: 채팅 로직 구현) ...
    return jsonify({"reply": "AI의 답변입니다."})
