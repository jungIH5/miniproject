from flask import Blueprint, request, jsonify, session, current_app
import google.generativeai as genai
from sqlalchemy import text

chat_bp = Blueprint('chat', __name__)

@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """
    [백엔드 리더 담당 구역] 
    제미나이를 활용한 1:1 뷰티 상담 서비스
    """
    if "user_id" not in session:
        return jsonify({"success": False, "error": "로그인이 필요합니다."}), 401
    
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "잘못된 요청입니다."}), 400

    api_key = current_app.config.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    message = data.get("message", "")
    context = data.get("context", "컨텍스트 정보가 없습니다.")
    history = data.get("history", [])

    # ────── [프롬프트 가드레일 설정] ────── #
    system_prompt = (
        "당신은 뷰티/퍼스널 컬러 전문 AI 컨설턴트 '벨라'입니다.\n\n"
        "[답변 필수 지침]\n"
        "1. 질문자가 '피부 개선, 화장품 추천, 퍼스널 컬러, 스타일링, 뷰티 습관'에 관해 물을 때만 전문적으로 답변하세요.\n"
        "2. 요리 메뉴 추천, 정치적 견해, 역사적 사실, 일반 상식 등 '뷰티와 무관한 질문'이 들어올 경우 다음과 같은 톤으로 정중히 거절하세요.\n"
        "   - 예시: '죄송합니다만, 저는 리님의 아름다움을 찾아드리는 뷰티 컨설턴트라서 그 부분은 도움을 드리기 어렵네요. 대신 피부 관리에 대해 궁금한 점이 있으시면 언제든 말씀해주세요!'\n"
        "3. 사용자의 현재 진단 정보 : " + str(context) + "\n"
        "4. 말투는 상냥하고 우아한 전문가의 어조를 유지하세요."
    )

    try:
        formatted_history = []
        if not history:
             formatted_history.append({"role": "user", "parts": [system_prompt]})
             formatted_history.append({"role": "model", "parts": ["반갑습니다! 당신의 아름다움을 찾아드릴 벨라입니다. 무엇을 도와드릴까요?"]})
        else:
            for item in history:
                formatted_history.append({"role": item.get("role", "user"), "parts": [item.get("text", "")]})
        
        chat_session = model.start_chat(history=formatted_history)
        response = chat_session.send_message(message)
        ai_response = response.text

        # ── 상담 내역 DB 저장 ──
        engine = current_app.extensions.get("db_engine")
        if engine:
            with engine.begin() as conn:
                mbr_id = int(session["user_id"])
                
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

        return jsonify({
            "success": True, 
            "response": ai_response
        })
        
    except Exception as e:
        current_app.logger.error(f"Chat Error: {e}")
        return jsonify({"success": False, "error": "AI가 잠시 휴식 중이에요. 다시 시도해 주세요!"}), 500
