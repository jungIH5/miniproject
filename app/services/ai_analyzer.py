import google.generativeai as genai
import json
import base64
from flask import current_app
from .skin_analysis import SkinAnalyzer

# 이미 생성된 분석 엔진 인스턴스 (메모리 효율을 위해 한 번만 생성)
_analyzer = SkinAnalyzer()

def analyze_skin_and_color(image_file):
    """
    [데이터/AI 구역] 백엔드에서 넘겨받은 사진으로 피부와 컬러를 분석합니다.
    """
    if not image_file:
        return {"success": False, "error": "이미지 파일이 없습니다."}

    # 1단계: 딥러닝 기반 피부 분석 (skin_analysis.py 활용)
    image_bytes = image_file.read()
    skin_result = _analyzer.analyze(image_bytes)

    if not skin_result.get("success"):
        return skin_result

    # 2단계: 제미나이(Gemini)를 활용한 퍼스널 컬러 및 종합 분석
    api_key = current_app.config["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # 이미지를 Base64로 인코딩하여 제미나이에게 전달
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    
    prompt = f"""
    당신은 숙련된 퍼스널 컬러 전문가이자 피부과 전문의입니다. 
    이미지를 분석하여 다음 JSON 형식으로만 답변해주세요.
    내용에 피부 분석 결과({json.dumps(skin_result['conditions'])})를 참고하여 종합적인 조언을 담아주세요.

    {{
      "color_result": {{
        "season": "봄 웜톤/여름 쿨톤/가을 웜톤/겨울 쿨톤 중 하나",
        "emoji": "해당 계절 이모지",
        "subtitle": "어울리는 대표 분위기 설명",
        "reasoning": [
          {{"factor": "피부톤", "value": "상세 수치", "detail": "이유"}},
          {{"factor": "눈동자/헤어", "value": "상세 수치", "detail": "이유"}}
        ],
        "palette": ["#색상코드1", "#색상코드2"],
        "avoid_palette": ["#색상코드1", "#색상코드2"]
      }},
      "ai_advice": "전체적인 피부와 컬러 조화에 대한 전문가의 따뜻한 조언 한마디"
    }}
    """

    try:
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])
        
        # JSON 결과 파싱
        ai_data_raw = response.text.replace("```json", "").replace("```", "").strip()
        ai_result = json.loads(ai_data_raw)
        
        # 3단계: 두 결과를 통합하여 변환
        final_result = {
            "success": True,
            "overall_score": skin_result["overall_score"],
            "skin_type": skin_result["skin_type"],
            "conditions": skin_result["conditions"],
            "recommendations": skin_result["recommendations"],
            "color_result": ai_result["color_result"],
            "ai_advice": ai_result["ai_advice"]
        }
        return final_result

    except Exception as e:
        print(f"AI 분석 중 오류: {e}")
        # AI 분석 실패 시 피부 분석 결과만이라도 반환 (Fallback)
        return skin_result
