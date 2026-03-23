from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app
from sqlalchemy import text
# 데이터 엔지니어의 구역인 ai_analyzer에서 함수를 가져옵니다.
from app.services.ai_analyzer import analyze_skin_and_color

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return render_template("index.html")

@main_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    [백엔드 역할] 1. 요청 받고 사진 추출, 2. AI 엔진 호출, 3. 결과 반환
    """
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401
    
    result = analyze_skin_and_color(request.files.get("image"))
    return jsonify(result)

@main_bp.route("/api/click-log", methods=["POST"])
def log_click():
    """
    [고도화 기능] 사용자가 상품을 클릭했을 때 DB에 기록
    """
    data = request.json
    user_id = session.get("user_id", "anonymous")
    product_name = data.get("product_name")
    product_link = data.get("product_link")

    if not product_name or not product_link:
        return jsonify({"success": False, "error": "데이터 부족"}), 400

    try:
        engine = current_app.extensions["db_engine"]
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO product_click_logs (user_id, product_name, product_link)
                VALUES (:user_id, :product_name, :product_link)
            """), {"user_id": user_id, "product_name": product_name, "product_link": product_link})
        return jsonify({"success": True})
    except Exception as e:
        current_app.logger.error(f"Click log error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
