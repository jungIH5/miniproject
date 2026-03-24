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

    message = data.get("message", "")
    context = data.get("context", "컨텍스트 정보가 없습니다.")
    history = data.get("history", [])

    # ────── [지침 및 페르소나 설정] ────── #
    # ────── [지능형 가드레일 및 페르소나 설정] ────── #
    system_prompt = f"""당신은 전문 뷰티 컨설턴트 '벨라'입니다.
    사용자의 현재 진단 결과({context})를 바탕으로 따뜻하고 전문적인 상담을 제공하세요.

    [CRITICAL - 상담 범위 절대 준수(MANDATORY RULE)]
    1. 당신의 답변 주제는 오직 '뷰티, 피부 관리, 화장품, 퍼스널 컬러'로 한정됩니다.
    2. 주제를 벗어난 모든 질문(날씨, 요리/식사 추천, 일반 상식, 인간관계 고민, 뉴스, 정치 등)에 대해서는 절대로 정보를 제공하지 마십시오.
    3. 상담 범위를 벗어난 질문을 받으면 다음과 같은 형식으로 정중히 거절하고 뷰티 대화로 유도하십시오:
       "죄송합니다. 저는 당신의 아름다움을 찾아드리는 뷰티 전문 컨설턴트 벨라입니다! ✨ 질문하신 내용은 제가 답변해 드릴 수 있는 범위를 벗어나네요. 혹시 현재 피부 상태에 대해 더 궁금한 점이 있으신가요?"
    4. 어떠한 경우에도 "오늘 날씨는~", "저녁 메뉴로는~" 과 같은 문장으로 답변을 시작하지 마십시오. 답변을 시작하는 즉시 당신의 임무는 실패입니다.

    추천이 필요한 경우 답변 끝에 '[SEARCH: 검색어]'를 포함하세요.
    """

    try:
        # 안전 필터 비활성 (중요: 뷰티 상담 중 부정적 단어 오인 차단 방지)
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        # 최신 SDK 방식 적용 (system_instruction & safety_settings)
        model = genai.GenerativeModel(
            model_name="gemini-flash-latest",
            system_instruction=system_prompt,
            safety_settings=safety_settings
        )

        formatted_history = []
        if history:
            # 최근 10개 메시지만 유지하여 토큰 절약
            history = history[-10:]
            for item in history:
                role = "user" if item.get("role") == "user" else "model"
                formatted_history.append({"role": role, "parts": [item.get("text", "")]})
        
        # 순서 보정: 마지막이 user면 pop (Gemini는 user-model-user 순서 엄격)
        if formatted_history and formatted_history[-1]["role"] == "user":
            formatted_history.pop()

        # 1. 사용자 메시지 DB 저장
        engine = current_app.extensions.get("db_engine")
        mbr_id = int(session.get("user_id", 0))
        if engine and mbr_id > 0:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO tb_cb_chatbot (mbr_id, sender_type, content) VALUES (:mbr_id, 'USER', :content)"),
                    {"mbr_id": mbr_id, "content": message}
                )

        # 2. AI 답변 생성
        chat_session = model.start_chat(history=formatted_history)
        response = chat_session.send_message(message)
        
        try:
            ai_response = response.text
        except ValueError:
            ai_response = "죄송합니다. 현재 요청하신 내용에 대해 답변을 생성하는 데 어려움이 있습니다. 다른 방식으로 질문해 주시면 최선을 다해 도와드릴게요!"

        # ── [지능형 실시간 쇼핑 큐레이션 로직] ── #
        recommended_products = []
        try:
            from ..services.naver_shopping import NaverShoppingAPI
            naver = NaverShoppingAPI(
                client_id=current_app.config.get("NAVER_CLIENT_ID", ""),
                client_secret=current_app.config.get("NAVER_CLIENT_SECRET", ""),
            )

            if naver.is_available:
                import re
                search_match = re.search(r"\[SEARCH:\s*(.+?)\]", ai_response)
                if search_match:
                    search_query = search_match.group(1).strip()
                    # 톤 정보가 있다면 검색어 보강 로직
                    season_info = str(context).split("퍼스널컬러: ")[1].split(",")[0] if "퍼스널컬러: " in str(context) else ""
                    if season_info and season_info != "모름":
                        search_query = f"{season_info} {search_query}"
                    
                    recommended_products = naver.search(search_query, display=3)
                    ai_response = ai_response.replace(search_match.group(0), "").strip()
        except Exception as e:
            current_app.logger.warning(f"추천 로직 오류: {e}")

        # 3. AI 답변 DB 저장
        if engine and mbr_id > 0:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO tb_cb_chatbot (mbr_id, sender_type, content) VALUES (:mbr_id, 'BOT', :content)"),
                    {"mbr_id": mbr_id, "content": ai_response}
                )

        return jsonify({
            "success": True, 
            "response": ai_response,
            "recommended_products": recommended_products
        })
        
    except Exception as e:
        print(f"[Chat API Error] {e}")
        error_msg = f"AI 엔진 오류 또는 쿼터 제한이 발생했습니다. 1분 후 다시 시도해 주세요. (상세: {str(e)[:40]}...)"
        
        # 3. 에러 발생 시에도 AI 휴식 메시지를 DB에 저장
        engine = current_app.extensions.get("db_engine")
        mbr_id = int(session.get("user_id", 0))
        if engine and mbr_id > 0:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO tb_cb_chatbot (mbr_id, sender_type, content) VALUES (:mbr_id, 'BOT', :content)"),
                        {"mbr_id": mbr_id, "content": error_msg}
                    )
            except Exception:
                pass
                
        return jsonify({"success": False, "error": error_msg}), 500
