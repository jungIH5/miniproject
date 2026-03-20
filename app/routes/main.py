from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
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
    [백엔드 역할] 
    1. 요청을 받고 사진 데이터 추출
    2. 데이터 엔지니어의 엔진(ai_analyzer) 호출
    3. 결과를 프론트엔드에 반환
    """
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401
        
    # 데이터 엔지니어의 로직 호출 (협업 인터페이스)
    result = analyze_skin_and_color(request.files.get("image"))
    return jsonify(result)
