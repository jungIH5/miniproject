"""AI 분석 총괄 모듈 (데이터/AI 담당 구역)

퍼스널컬러 + 피부 분석 + AI 상담을 통합 관리합니다.
백엔드(routes)에서는 이 모듈의 함수만 호출하면 됩니다.

[개선사항 - 2026-03-20]
1. personal_color.py 로컬 분석을 1차로 실행 → Gemini 비전을 2차 보완으로 활용
   - 이유: Gemini API 실패/할당량 초과 시에도 결과 보장
2. Gemini 모델을 gemini-2.0-flash로 변경 (무료 + 최신)
3. chat() 함수 추가 — 진단 결과 기반 멀티턴 AI 상담
4. 싱글톤 패턴으로 CNN 모델 중복 로딩 방지
"""

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
    """
    [데이터/AI 구역] 백엔드에서 넘겨받은 사진으로 피부와 컬러를 분석합니다.

    파이프라인:
      1단계: CNN + OpenCV 피부 분석 (skin_analysis.py)
      2단계: 로컬 퍼스널컬러 분석 (personal_color.py) — 항상 실행
      3단계: Gemini 비전 보완 분석 — 실패해도 2단계 결과로 폴백
    """
    if not image_file:
        return {"success": False, "error": "이미지 파일이 없습니다."}

    image_bytes = image_file.read()

    # ── 1단계: 딥러닝 기반 피부 분석 (MobileNetV2 CNN + OpenCV) ──
    skin_result = _get_skin_analyzer().analyze(image_bytes)

    if not skin_result.get("success"):
        return skin_result

    # ── 2단계: 로컬 퍼스널컬러 분석 (API 불필요, 항상 성공) ──
    # [개선] 기존에는 Gemini만으로 컬러 분석했으나,
    # API 실패 시 컬러 결과가 아예 없는 문제 → 로컬 분석을 기본값으로 확보
    local_color = _get_color_analyzer().analyze(image_bytes)

    # ── 3단계: Gemini 비전으로 퍼스널컬러 보완 + 종합 조언 ──
    # [개선] Gemini가 성공하면 더 정교한 결과로 교체, 실패하면 로컬 결과 유지
    gemini_color, ai_advice = _gemini_color_analysis(image_bytes, skin_result)

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
    }
    return final_result


def _gemini_color_analysis(image_bytes, skin_result):
    """Gemini 비전 API로 퍼스널컬러 + 종합 조언 생성

    Returns
    -------
    (color_result_dict or None, ai_advice_str or None)
    """
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        return None, None

    try:
        genai.configure(api_key=api_key)
        # [개선] gemini-1.5-flash → gemini-2.0-flash (무료 + 최신 + 더 정확)
        model = genai.GenerativeModel("gemini-2.0-flash")

        # 피부 분석 조건을 JSON으로 직렬화하여 프롬프트에 포함
        conditions_json = json.dumps(skin_result.get("conditions", {}), ensure_ascii=False)

        prompt = f"""
        당신은 숙련된 퍼스널 컬러 전문가이자 피부과 전문의입니다.
        이미지를 분석하여 다음 JSON 형식으로만 답변해주세요.
        내용에 피부 분석 결과({conditions_json})를 참고하여 종합적인 조언을 담아주세요.

        {{
          "color_result": {{
            "success": true,
            "season": "봄 웜톤/여름 쿨톤/가을 웜톤/겨울 쿨톤 중 하나",
            "season_key": "spring_warm/summer_cool/autumn_warm/winter_cool 중 하나",
            "emoji": "해당 계절 이모지",
            "subtitle": "어울리는 대표 분위기 설명",
            "reasoning": [
              {{"factor": "피부톤", "value": "상세 분석", "detail": "이유"}},
              {{"factor": "눈동자/헤어", "value": "상세 분석", "detail": "이유"}}
            ],
            "best_colors": ["어울리는 색상 6개"],
            "color_codes": ["#hex 6개"],
            "worst_colors": ["피할 색상 4개"],
            "worst_color_codes": ["#hex 4개"],
            "makeup_tip": "메이크업 팁",
            "fashion_tip": "패션 팁"
          }},
          "ai_advice": "전체적인 피부와 컬러 조화에 대한 전문가의 따뜻한 조언 (2-3문장)"
        }}
        """

        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])

        # JSON 결과 파싱
        ai_data_raw = response.text.replace("```json", "").replace("```", "").strip()
        ai_result = json.loads(ai_data_raw)

        return ai_result.get("color_result"), ai_result.get("ai_advice")

    except Exception as e:
        # [개선] Gemini 실패 시 로그만 남기고 None 리턴 → 로컬 분석으로 폴백
        print(f"[AI] Gemini 컬러 분석 실패 (로컬 분석으로 폴백): {e}")
        return None, None


# ================================================================
# AI 상담 함수 — routes/chat.py 또는 api/chat.py 에서 호출
# ================================================================

def chat(message: str, context: str = "", history: list = None) -> dict:
    """
    [데이터/AI 구역] Gemini 기반 AI 뷰티 상담

    Parameters
    ----------
    message : 사용자 메시지
    context : 진단 결과 요약 (첫 대화 시 주입)
    history : 이전 대화 기록 [{role, text}, ...]

    Returns
    -------
    dict with keys: success, response
    """
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        return {"success": False, "error": "Gemini API 키가 설정되지 않았습니다."}

    if history is None:
        history = []

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        formatted_history = []

        # 첫 대화: 시스템 프롬프트로 역할 부여 + 진단 컨텍스트 주입
        if not history:
            system_prompt = (
                f"당신은 친절하고 전문적인 뷰티/퍼스널컬러 컨설턴트입니다. "
                f"현재 사용자의 진단 정보는 다음과 같습니다:\n"
                f"{context}\n\n"
                f"이 정보를 바탕으로 사용자의 질문에 답하고 화장품, 스타일링 등 맞춤형 조언을 해주세요. "
                f"말투는 친근하게 하고, 너무 길지 않게 요점만 설명하세요."
            )
            formatted_history.append({"role": "user", "parts": [system_prompt]})
            formatted_history.append({
                "role": "model",
                "parts": ["네, 알겠습니다! 진단 결과를 바탕으로 친절하게 상담해드리겠습니다. 질문을 남겨주세요!"],
            })
        else:
            for item in history:
                formatted_history.append({
                    "role": item.get("role", "user"),
                    "parts": [item.get("text", "")],
                })

        chat_session = model.start_chat(history=formatted_history)
        response = chat_session.send_message(message)

        return {"success": True, "response": response.text}

    except Exception as e:
        return {"success": False, "error": f"AI 응답 중 오류: {str(e)}"}
