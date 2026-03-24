"""진단 API 엔드포인트

POST /api/diagnosis
  - multipart/form-data 로 image 필드에 사진 첨부
  - 퍼스널컬러 + 피부 상태 분석 + 실제 제품 추천을 JSON 으로 반환
  - 웹 프론트엔드 & 모바일 APK 앱 모두 이 API 를 사용

[개선] ai_analyzer 통합 모듈을 통해 분석 호출하도록 변경
"""

import uuid

from flask import current_app, request, session
from sqlalchemy import text
import json

from . import api_blueprint
from ..services import ai_analyzer
from ..services.naver_shopping import NaverShoppingAPI

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@api_blueprint.post("/diagnosis")
def run_diagnosis():
    """사진을 업로드하여 퍼스널컬러 + 피부 상태 진단 + 제품 추천"""

    # ── [고도화] 비로그인 사용자 처리 보완 ──
    if "user_id" not in session:
        return {"success": False, "error": "로그인이 필요한 서비스입니다. 팀장님 말씀대로 비로그인 유저는 막았습니다."}, 401

    # ── 입력 검증 ──
    if "image" not in request.files:
        return {"success": False, "error": "이미지가 첨부되지 않았습니다."}, 400

    file = request.files["image"]
    if file.filename == "":
        return {"success": False, "error": "파일이 선택되지 않았습니다."}, 400

    if not _allowed(file.filename):
        return {
            "success": False,
            "error": "지원하지 않는 파일 형식입니다. (PNG, JPG, JPEG, WebP 만 가능)",
        }, 400

    # ── 1+2. AI 통합 분석 (퍼스널컬러 + 피부) ──
    # [개선] ai_analyzer.analyze_skin_and_color() 하나로 통합 호출
    result = ai_analyzer.analyze_skin_and_color(file)

    if not result.get("success"):
        return result, 500

    # ── 3. 네이버 쇼핑 API로 실제 제품 검색 ──
    naver = NaverShoppingAPI(
        client_id=current_app.config.get("NAVER_CLIENT_ID", ""),
        client_secret=current_app.config.get("NAVER_CLIENT_SECRET", ""),
    )

    color_products = []
    skin_products = []
    
    # result["personal_color"] 키일 수도 있으니 안전하게 가져옴 (방금 짠 AI Analyzer 참고)
    color_result = result.get("color_result", {})
    if not color_result:
        # 혹시 ai_analyzer 변경으로 키가 personal_color로 바뀐 경우
        color_result = result.get("personal_color", {})

        if color_result:
            color_products = naver.search_color_products(
                color_result.get("season_key", "")
            )
            
        skin_cond = result.get("conditions", {})
        if skin_cond:
             skin_products = naver.search_skin_products(skin_cond)

    # ── 4. 진단 결과 DB 저장: tb_sk_diagnosis 테이블에 누락된 컬럼(tone 등) 추가 ──
    session_id = str(uuid.uuid4())
    try:
        engine = current_app.extensions.get("db_engine")
        if engine:
            with engine.begin() as conn:
                mbr_id = session.get("user_id")
                cond = result.get("conditions", {})
                
                # 팀장님 PR에 있던 톤/명도/채도 데이터 추출 로직
                reasoning = color_result.get("reasoning", [])
                tone_info = next((r for r in reasoning if r.get("factor") == "언더톤"), {})
                bright_info = next((r for r in reasoning if r.get("factor") == "명도"), {})
                chrome_info = next((r for r in reasoning if r.get("factor") == "채도"), {})
                
                conn.execute(
                    text("""
                        INSERT INTO tb_sk_diagnosis (
                            mbr_id, color, color_note, color_rmk,
                            tone, tone_rmk, bright, bright_rmk, chrome, chrome_rmk,
                            type, type_score, type_rmk,
                            bright_score, bright_score_rmk,
                            equality_score, equality_score_rmk,
                            trouble_score, trouble_score_rmk,
                            texture_score, texture_score_rmk,
                            moisture_score, moisture_score_rmk,
                            balance_score, balance_score_rmk,
                            match_color, unmatch_color
                        ) VALUES (
                            :mbr_id, :color, :color_note, :color_rmk,
                            :tone, :tone_rmk, :bright, :bright_rmk, :chrome, :chrome_rmk,
                            :type, :type_score, :type_rmk,
                            :bright_score, :bright_score_rmk,
                            :equality_score, :equality_score_rmk,
                            :trouble_score, :trouble_score_rmk,
                            :texture_score, :texture_score_rmk,
                            :moisture_score, :moisture_score_rmk,
                            :balance_score, :balance_score_rmk,
                            :match_color, :unmatch_color
                        )
                    """),
                    {
                        "mbr_id": mbr_id,
                        "color": color_result.get("season_key", ""),
                        "color_note": color_result.get("season", ""),
                        "color_rmk": json.dumps(reasoning, ensure_ascii=False),
                        "tone": tone_info.get("value", ""),
                        "tone_rmk": tone_info.get("detail", ""),
                        "bright": bright_info.get("value", ""),
                        "bright_rmk": bright_info.get("detail", ""),
                        "chrome": chrome_info.get("value", ""),
                        "chrome_rmk": chrome_info.get("detail", ""),
                        "type": result.get("skin_type", {}).get("name", ""),
                        "type_score": result.get("overall_score", 0),
                        "type_rmk": result.get("skin_type", {}).get("description", ""),
                        "bright_score": cond.get("brightness", {}).get("score", 0),
                        "bright_score_rmk": cond.get("brightness", {}).get("detail", ""),
                        "equality_score": cond.get("evenness", {}).get("score", 0),
                        "equality_score_rmk": cond.get("evenness", {}).get("detail", ""),
                        "trouble_score": cond.get("redness", {}).get("score", 0),
                        "trouble_score_rmk": cond.get("redness", {}).get("detail", ""),
                        "texture_score": cond.get("texture", {}).get("score", 0),
                        "texture_score_rmk": cond.get("texture", {}).get("detail", ""),
                        "moisture_score": cond.get("moisture", {}).get("score", 0),
                        "moisture_score_rmk": cond.get("moisture", {}).get("detail", ""),
                        "balance_score": cond.get("oiliness", {}).get("score", 0),
                        "balance_score_rmk": cond.get("oiliness", {}).get("detail", ""),
                        "match_color": json.dumps(color_result.get("best_colors", []), ensure_ascii=False),
                        "unmatch_color": json.dumps(color_result.get("worst_colors", []), ensure_ascii=False)
                    }
                )
    except Exception:
        pass

    return {
        "success": True,
        "session_id": session_id,
        "personal_color": color_result,
        "skin_analysis": {
            "success": True,
            "overall_score": result.get("overall_score"),
            "skin_type": result.get("skin_type"),
            "conditions": result.get("conditions"),
            "recommendations": result.get("recommendations"),
            "analysis_method": result.get("analysis_method"),
        },
        "product_reasons": result.get("product_reasons", {}),
        "ai_advice": result.get("ai_advice", ""),
        "color_products": color_products,
        "skin_products": skin_products,
    }



