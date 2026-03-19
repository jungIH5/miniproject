import os
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")

from flask import current_app, request
import google.generativeai as genai

from . import api_blueprint

@api_blueprint.post("/chat")
def handle_chat():
    """제미나이를 활용한 AI 뷰티 상담 API"""
    data = request.json
    if not data:
        return {"success": False, "error": "잘못된 요청입니다."}, 400

    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        return {"success": False, "error": "제미나이 API 키가 등록되지 않았습니다. .env 파일을 확인해주세요."}, 500

    message = data.get("message", "")
    context = data.get("context", "컨텍스트 정보가 없습니다.")
    history = data.get("history", [])

    try:
        genai.configure(api_key=api_key)
        
        # 호환성 문제 방지를 위해 -latest 나 gemini-1.5-flash-latest 모델을 사용
        model = genai.GenerativeModel("gemini-flash-latest")

        # 제미나이의 히스토리 포맷(user/model, parts)에 맞춰 변환
        formatted_history = []
        
        # 첫 대화라면 시스템 프롬프트(역할 부여) 강제 주입
        if not history:
            system_prompt = (
                f"당신은 친절하고 전문적인 뷰티/퍼스널컬러 컨설턴트입니다. "
                f"현재 사용자의 진단 정보는 다음과 같습니다:\n"
                f"{context}\n\n"
                f"이 정보를 바탕으로 사용자의 질문에 답하고 화장품, 스타일링 등 맞춤형 조언을 해주세요. "
                f"말투는 친근하게 하고, 너무 길지 않게 요점만 설명하세요."
            )
            formatted_history.append({"role": "user", "parts": [system_prompt]})
            formatted_history.append({"role": "model", "parts": ["네, 알겠습니다! 전문적인 뷰티 컨설턴트로서 진단 결과를 바탕으로 친절하게 상담해드리겠습니다. 질문을 남겨주세요! 😊"]})
        else:
            for item in history:
                formatted_history.append({
                    "role": item.get("role", "user"),
                    "parts": [item.get("text", "")]
                })
        
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(message)
        
        return {
            "success": True, 
            "response": response.text
        }
        
    except Exception as e:
        return {"success": False, "error": f"AI 응답 중 오류가 발생했습니다: {str(e)}"}, 500
