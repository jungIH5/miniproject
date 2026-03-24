import os, uuid
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import text
from app.services.ai_analyzer import analyze_skin_and_color

AVATAR_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return render_template("index.html")

@main_bp.route("/analyze", methods=["POST"])
def analyze():
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    result = analyze_skin_and_color(request.files.get("image"))

    # 분석 결과 DB 저장
    if result.get("success"):
        try:
            engine = current_app.extensions["db_engine"]
            pc = result.get("color_result") or {}
            sk = result.get("skin_analysis") or {}
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO diagnosis_results
                        (session_id, personal_color_season, skin_type, overall_score, analysis_method)
                    VALUES (:sid, :color, :skin, :score, :method)
                """), {
                    "sid": str(session.get("user_id")),
                    "color": pc.get("season", ""),
                    "skin": (sk.get("skin_type") or {}).get("name", ""),
                    "score": result.get("overall_score", 0),
                    "method": result.get("analysis_method", "basic")
                })
        except Exception as e:
            current_app.logger.error(f"진단 결과 저장 오류: {e}")

    return jsonify(result)


@main_bp.route("/api/profile/history")
def profile_history():
    if "user_id" not in session:
        return jsonify({"error": "로그인 필요"}), 401
    try:
        engine = current_app.extensions["db_engine"]
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, personal_color_season, skin_type, overall_score, analysis_method, created_at
                FROM diagnosis_results
                WHERE session_id = :sid
                ORDER BY created_at DESC
                LIMIT 20
            """), {"sid": str(session["user_id"])}).fetchall()
        return jsonify({"success": True, "history": [
            {"id": r[0], "color": r[1], "skin": r[2], "score": r[3], "method": r[4], "date": str(r[5])}
            for r in rows
        ]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@main_bp.route("/api/profile/update", methods=["POST"])
def profile_update():
    if "user_id" not in session:
        return jsonify({"error": "로그인 필요"}), 401
    data = request.json
    new_name  = data.get("name", "").strip()
    new_email = data.get("email", "").strip()
    new_pwd   = data.get("password", "").strip()
    try:
        from werkzeug.security import generate_password_hash
        engine = current_app.extensions["db_engine"]
        with engine.begin() as conn:
            if new_name:
                conn.execute(text("UPDATE tb_cs_member SET mbr_name=:n WHERE mbr_id=:id"),
                             {"n": new_name, "id": session["user_id"]})
                session["username"] = new_name
            if new_email:
                conn.execute(text("UPDATE tb_cs_member SET mbr_email=:e WHERE mbr_id=:id"),
                             {"e": new_email, "id": session["user_id"]})
                session["user_email"] = new_email
            if new_pwd:
                conn.execute(text("UPDATE tb_cs_member SET mbr_pwd=:p WHERE mbr_id=:id"),
                             {"p": generate_password_hash(new_pwd), "id": session["user_id"]})
        return jsonify({"success": True,
                        "name": session.get("username"),
                        "email": session.get("user_email")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@main_bp.route("/api/profile/avatar", methods=["POST"])
def profile_avatar():
    if "user_id" not in session:
        return jsonify({"error": "로그인 필요"}), 401
    file = request.files.get("avatar")
    if not file or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "지원하지 않는 파일 형식입니다."}), 400
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{session['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = os.path.join(AVATAR_UPLOAD_DIR, filename)
    os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)
    # 기존 아바타 파일 삭제
    old_photo = session.get("user_photo", "")
    if old_photo:
        old_path = os.path.join(AVATAR_UPLOAD_DIR, os.path.basename(old_photo))
        if os.path.exists(old_path):
            os.remove(old_path)
    file.save(save_path)
    photo_url = f"/static/uploads/avatars/{filename}"
    try:
        engine = current_app.extensions["db_engine"]
        with engine.begin() as conn:
            conn.execute(text("UPDATE tb_cs_member SET mbr_photo=:p WHERE mbr_id=:id"),
                         {"p": photo_url, "id": session["user_id"]})
        session["user_photo"] = photo_url
        return jsonify({"success": True, "photo_url": photo_url})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
