from flask import Blueprint, request, session, redirect, url_for, flash, current_app, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
import requests
import secrets

auth_bp = Blueprint('auth', __name__)

# --- [백엔드 담당 구역] 소셜 로그인 설정 ---
NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USERINFO_URL = "https://openapi.naver.com/v1/nid/me"

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mbr_name, mbr_pwd = request.form.get("username"), request.form.get("password")
        engine = current_app.extensions["db_engine"]
        with engine.begin() as conn:
            user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_pwd, mbr_email FROM tb_cs_members WHERE mbr_name = :name"), {"name": mbr_name}).fetchone()
            if user and check_password_hash(user[2], mbr_pwd):
                session.update({"user_id": user[0], "username": user[1], "user_email": user[3]})
                return redirect(url_for("main.index"))
            flash("아이디 또는 비밀번호가 틀렸습니다.", "error")
    return render_template("login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # (회원가입 로직 구현...)
        pass
    return render_template("signup.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))

@auth_bp.route("/naver/callback")
def naver_callback():
    code, state = request.args.get("code"), request.args.get("state")
    if state != session.get("naver_state"):
        flash("세션이 만료되었습니다.", "error")
        return redirect(url_for("auth.login"))

    token_res = requests.post(NAVER_TOKEN_URL, data={
        "grant_type": "authorization_code", "client_id": current_app.config["NAVER_LOGIN_ID"],
        "client_secret": current_app.config["NAVER_LOGIN_SECRET"], "code": code, "state": state
    }).json()
    
    user_res = requests.get(NAVER_USERINFO_URL, headers={"Authorization": f"Bearer {token_res.get('access_token')}"}).json()
    profile = user_res.get("response")
    email = profile.get("email")
    
    engine = current_app.extensions["db_engine"]
    with engine.begin() as conn:
        user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_email FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        if not user:
            temp_name = f"naver_{profile.get('id')[:8]}"
            conn.execute(text("INSERT INTO tb_cs_members (mbr_name, mbr_pwd, mbr_email, mbr_status) VALUES (:name, :pwd, :email, 'active')"),
                         {"name": temp_name, "pwd": "SOCIAL_LOGIN_NAVER", "email": email})
            user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_email FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        session.update({"user_id": user[0], "username": user[1], "user_email": user[2]})
    return redirect(url_for("main.index"))

# (구글, 카카오 콜백 로직 동일하게 추가... 백엔드에서 필요한 모든 기능 총망라)
