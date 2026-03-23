import json
import base64
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")

import google.generativeai as genai
from flask import current_app

from .skin_analysis import SkinAnalyzer
from .personal_color import PersonalColorAnalyzer

# ── 싱글톤 인스턴스 (CNN 모델 중복 로딩 방지) ──
_skin_analyzer = None
_color_analyzer = None


def _get_skin_analyzer():
    global _skin_analyzer
    if _skin_analyzer is None:
        _skin_analyzer = SkinAnalyzer()
    return _skin_analyzer


def _get_color_analyzer():
    global _color_analyzer
    if _color_analyzer is None:
        _color_analyzer = PersonalColorAnalyzer()
    return _color_analyzer


# ================================================================
# 메인 분석 함수 — routes/main.py 에서 호출
# ================================================================

def analyze_skin_and_color(image_file):
    if not image_file:
        return {"success": False, "error": "이미지 파일이 없습니다."}

    image_bytes = image_file.read()

    # ── 1단계: 딥러닝 기반 피부 분석 ──
    skin_result = _get_skin_analyzer().analyze(image_bytes)

    if not skin_result.get("success"):
        return skin_result

    # ── 2단계: 로컬 퍼스널컬러 분석 ──
    local_color = _get_color_analyzer().analyze(image_bytes)

    # ── 3단계: Gemini 비전으로 퍼스널컬러 보완 + 종합 조언 + [추가] 쇼핑 검색어 생성 ──
    gemini_color, ai_advice, shop_queries = _gemini_color_analysis_v2(image_bytes, skin_result)

    # Gemini 성공 시 → Gemini 컬러 결과 사용, 실패 시 → 로컬 결과 유지
    color_result = gemini_color if gemini_color else local_color
    
    # ── 최종 결과 통합 ──
    final_result = {
        "success": True,
        "overall_score": skin_result["overall_score"],
        "skin_type": skin_result["skin_type"],
        "conditions": skin_result["conditions"],
        "recommendations": skin_result["recommendations"],
        "analysis_method": skin_result.get("analysis_method", "basic"),
        "color_result": color_result,
        "ai_advice": ai_advice or "피부 분석이 완료되었습니다. AI 상담에서 더 자세한 조언을 받아보세요!",
        "shop_queries": shop_queries # [업그레이드] 실시간 생성된 검색어 리스트
    }
    return final_result


def _gemini_color_analysis_v2(image_bytes, skin_result):
    """Gemini 비전 API로 퍼스널컬러 + 종합 조언 + 쇼핑 검색어 생성"""
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        return None, None, []

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        conditions_json = json.dumps(skin_result.get("conditions", {}), ensure_ascii=False)

        prompt = f"""
        당신은 숙련된 퍼스널 컬러 전문가이자 피부과 전문의입니다.
        이미지를 분석하여 다음 JSON 형식으로만 답변해주세요.
        내용에 피부 분석 결과({conditions_json})를 참고하여 종합적인 조언을 담아주세요.
        특히, 사용자의 피부 고민을 해결할 수 있는 '네이버 쇼핑 검색어' 3개를 함께 생성해주세요.

        {{
          "color_result": {{
            "success": true,
            "season": "봄 웜톤/여름 쿨톤/가을 웜톤/겨울 쿨톤 중 하나",
            "season_key": "spring_warm/summer_cool/autumn_warm/winter_cool 중 하나",
            "emoji": "🌸",
            "subtitle": "어울리는 대표 분위기 설명",
            "reasoning": [
              {{"factor": "피부톤", "value": "상세 분석", "detail": "이유"}}
            ],
            "best_colors": ["색상 6개"],
            "color_codes": ["#hex 6개"],
            "worst_colors": ["4개"],
            "worst_color_codes": ["#hex 4개"],
            "makeup_tip": "팁",
            "fashion_tip": "팁"
          }},
          "ai_advice": "전문가의 따뜻한 조언",
          "shop_queries": [
            "검색어1 (예: 수분 부족형 지성을 위한 젤 크림)",
            "검색어2 (예: 봄웜톤 코랄 립 틴트)",
            "검색어3 (예: 민감성 피부 진정 시카 토너)"
          ]
        }}
        """

        response = model.generate_content([
            prompt,
            {"mime_type": "image/*", "data": image_bytes}
        ])

        ai_data_raw = response.text.replace("```json", "").replace("```", "").strip()
        ai_result = json.loads(ai_data_raw)

        return ai_result.get("color_result"), ai_result.get("ai_advice"), ai_result.get("shop_queries", [])

    except Exception as e:
        print(f"[AI] Gemini 분석 실패: {e}")
        return None, None, []


# AI 상담 함수
def chat(message: str, context: str = "", history: list = None) -> dict:
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key: return {"success": False, "error": "API Key missing"}

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        formatted_history = []
        if not history:
            system_prompt = f"전문 뷰티 컨설턴트 역할. 컨텍스트: {context}"
            formatted_history.append({"role": "user", "parts": [system_prompt]})
            formatted_history.append({"role": "model", "parts": ["준비되었습니다. 질문주세요!"]})
        else:
            for item in history:
                formatted_history.append({"role": item.get("role", "user"), "parts": [item.get("text", "")]})
        chat_session = model.start_chat(history=formatted_history)
        response = chat_session.send_message(message)
        return {"success": True, "response": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}
