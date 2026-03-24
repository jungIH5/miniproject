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
    
    # 원본 이미지 원격 전송용 Base64 (가상 메이크업 베이스)
    base64_original = base64.b64encode(image_bytes).decode('utf-8')

    # ── 1단계: 딥러닝 기반 피부 분석 ──
    skin_result = _get_skin_analyzer().analyze(image_bytes)

    if not skin_result.get("success"):
        return skin_result

    # ── 2단계: 로컬 퍼스널컬러 분석 ──
    _get_color_analyzer()
    local_color = _get_color_analyzer().analyze(image_bytes)

    # ── 3단계: Gemini 비전으로 퍼스널컬러 보완 + 종합 조언 ──
    gemini_color, ai_advice, shop_queries, product_reasons = _gemini_color_analysis_v2(image_bytes, skin_result)

    # Gemini 성공 시 → Gemini 컬러 결과 사용, 실패 시 → 로컬 결과 유지
    color_result = gemini_color if gemini_color else local_color
    
    final_result = {
        "success": True,
        "overall_score": skin_result["overall_score"],
        "skin_type": skin_result["skin_type"],

        "conditions": skin_result["conditions"],
        "recommendations": skin_result["recommendations"],
        "analysis_method": skin_result.get("analysis_method", "basic"),
        "color_result": color_result,
        "product_reasons": product_reasons,
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
        model = genai.GenerativeModel("gemini-flash-latest")

        conditions_json = json.dumps(skin_result.get("conditions", {}), ensure_ascii=False)

        prompt = f"""
        당신은 숙련된 퍼스널 컬러 전문가이자 수석 피부과 전문의입니다.
        이미지를 분석하여 다음 JSON 형식으로만 답변하되, 아래 지침을 엄격히 준수하세요.

        [분석 지침]
        1. 피부 분석 결과({conditions_json})를 참고하여 상세한 전문가 소견을 작성하세요.
        2. 'product_reasons' 항목에서 피부 점수가 **가장 낮은 상위 2개 지표**를 실명(예: 수분, 주름 등)으로 언급하여 분석의 전문성을 높이세요.
        3. 퍼스널 컬러와 제품 색상 간의 조화를 논리적으로 설명하세요.

        {{
          "color_result": {{
            "success": true,
            "season": "봄 웜톤/여름 쿨톤/가을 웜톤/겨울 쿨톤 중 하나",
            "season_key": "spring_warm/summer_cool/autumn_warm/winter_cool 중 하나",
            "emoji": "🌸",
            "subtitle": "어울리는 대표 분위기 설명",
            "reasoning": [
              {{"factor": "언더톤", "value": "분석 결과", "detail": "이유"}},
              {{"factor": "명도", "value": "분석 결과", "detail": "이유"}},
              {{"factor": "채도", "value": "분석 결과", "detail": "이유"}}
            ],
            "best_colors": ["색상 6개"],
            "color_codes": ["#hex 6개"],
            "worst_colors": ["4개"],
            "worst_color_codes": ["#hex 4개"],
            "makeup_tip": "팁",
            "fashion_tip": "팁"
          }},
          "product_reasons": {{
            "color_product_title": "✨ [전문화된 추천 제목 생성]",
            "color_products": "퍼스널 컬러의 특성을 고려하여 이 제품군이 왜 잘 어울리는지 설명하세요.",
            "skin_product_title": "🩺 [진단 기반 맞춤 제목 생성]",
            "skin_products": "가장 점수가 낮은 2가지 지표를 언급하며 그에 따른 전문적인 스킨케어 처방 이유를 설명하세요."
          }},
          "ai_advice": "전문가의 따뜻한 조언",
          "shop_queries": [
            "검색어1",
            "검색어2",
            "검색어3"
          ]
        }}
        """

        response = model.generate_content([
            prompt,
            {"mime_type": "image/*", "data": image_bytes}
        ])

        ai_data_raw = response.text.replace("```json", "").replace("```", "").strip()
        ai_result = json.loads(ai_data_raw)

        # ── 기본값 보정 (AI 실패 대비) ──
        reasons = ai_result.get("product_reasons", {})
        reasons.setdefault("color_product_title", "✨ 퍼스널 컬러 기반 맞춤 큐레이션")
        reasons.setdefault("color_products", f"분석된 {color_result.get('season', '컬러')} 톤의 피부 톤과 조화를 이루어, 얼굴에 형광등을 켠 듯 생기를 더해줄 최적의 색조 라인업을 구성했습니다.")
        reasons.setdefault("skin_product_title", "🩺 피부 전문 진단 기반 상품 추천")
        reasons.setdefault("skin_products", "현재 피부 상태의 가장 시급한 문제를 해결하고 유수분 밸런스를 즉각적으로 잡아줄 수 있는 전문 기능성 스킨케어입니다.")

        return (
            ai_result.get("color_result"),
            ai_result.get("ai_advice"),
            ai_result.get("shop_queries", []),
            reasons
        )

    except Exception as e:
        print(f"[AI] Gemini 분석 실패: {e}")
        # 실패 시 최소한의 기본 데이터 세트 반환
        fallback_reasons = {
            "color_product_title": "💄 어울리는 화장품 추천",
            "color_products": "퍼스널 컬러 분석 결과에 따라 어울리는 메이크업 제품을 추천합니다.",
            "skin_product_title": "🧴 추천 상품항목",
            "skin_products": "피부 상태를 고려하여 효과적인 스킨케어 제품을 추천합니다."
        }
        return None, "현재 AI 분석 서버가 혼잡하여 기본 조언을 제공해 드립니다.", [], fallback_reasons


# AI 상담 함수
def chat(message: str, context: str = "", history: list = None) -> dict:
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key: return {"success": False, "error": "API Key missing"}

    # ── [지침] ── #
    system_prompt = f"""당신은 전문 뷰티 컨설턴트 '벨라'입니다. 
    사용자의 진단 결과(컨텍스트: {context})를 바탕으로 따뜻하고 전문적인 상담을 제공하세요.
    최근 진단 이력이 있다면 그 추이(수분 상승/하락 등)를 언급하여 공감을 이끌어내세요.
    추천이 필요한 경우 답변 끝에 '[SEARCH: 검색어]'를 붙이세요. (일반 대화 시 금지)
    """

    try:
        genai.configure(api_key=api_key)
        
        # 안전 필터 비활성화 (뷰티 상담 중 부정적 단어 오인 방지)
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        # system_instruction 지원되는 최신 방식 사용 (안정성 강화)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_prompt,
            safety_settings=safety_settings
        )

        formatted_history = []
        if history:
            # 최근 10개 메시지만 유지하여 토큰 절약 (할당량 관리용)
            history = history[-10:]
            for item in history:
                role = "user" if item.get("role") == "user" else "model"
                formatted_history.append({"role": role, "parts": [item.get("text", "")]})
        
        # 히스토리 순서 보장 (Gemini는 user-model-user 순서를 엄격히 요구함)
        if formatted_history and formatted_history[-1]["role"] == "user":
            formatted_history.pop() # 중복된 마지막 유저 메시지 방지
            
        chat_session = model.start_chat(history=formatted_history)
        response = chat_session.send_message(message)
        
        # 응답 텍스트 추출 시도 (안전 필터로 인해 내용이 비었을 경우 대비)
        try:
            ai_text = response.text
        except ValueError:
            # 안전 필터에 의한 차단 발생 시
            ai_text = "죄송합니다. 요청하신 내용에 대해 벨라가 답변을 생성하는 데 어려움을 겪고 있어요. 다른 방식으로 질문해 주시겠어요?"

        return {"success": True, "response": ai_text}
    except Exception as e:
        print(f"[AI Chat Error] {e}") # 서버 로그 확인용
        return {"success": False, "error": f"분석 서버 부하 또는 쿼터 제한이 발생했습니다. 잠시 후 다시 시도해 주세요. (상세: {str(e)[:50]}...)"}
