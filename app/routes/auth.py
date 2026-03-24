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
            user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_pwd, mbr_email, mbr_photo FROM tb_cs_member WHERE mbr_name = :name"), {"name": mbr_name}).fetchone()
            if user and check_password_hash(user[2], mbr_pwd):
                session.update({"user_id": user[0], "username": user[1], "user_email": user[3], "user_photo": user[4] or ""})
                return redirect(url_for("main.index"))
            flash("아이디 또는 비밀번호가 틀렸습니다.", "error")
    return render_template("login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        mbr_name = request.form.get("username")
        mbr_pwd = request.form.get("password")
        mbr_email = request.form.get("email")
        
        hashed_pwd = generate_password_hash(mbr_pwd)
        engine = current_app.extensions["db_engine"]
        
        try:
            with engine.begin() as conn:
                existing = conn.execute(
                    text("SELECT 1 FROM tb_cs_member WHERE mbr_name = :name"),
                    {"name": mbr_name}
                ).fetchone()
                
                if existing:
                    flash("이미 존재하는 아이디입니다.", "error")
                else:
                    conn.execute(
                        text("""
                            INSERT INTO tb_cs_member (mbr_name, mbr_pwd, mbr_email, mbr_status)
                            VALUES (:name, :pwd, :email, 'active')
                        """),
                        {"name": mbr_name, "pwd": hashed_pwd, "email": mbr_email}
                    )
                    flash("회원가입이 완료되었습니다! 로그인해주세요.", "success")
                    return redirect(url_for("auth.login"))
        except Exception as e:
            flash(f"가입 중 오류가 발생했습니다: {e}", "error")
    return render_template("signup.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/naver/login")
def naver_login():
    state = secrets.token_hex(16)
    session["naver_state"] = state
    redirect_uri = url_for("auth.naver_callback", _external=True)
    client_id = current_app.config.get("NAVER_LOGIN_ID", "")
    auth_url = f"{NAVER_AUTH_URL}?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}"
    return redirect(auth_url)

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
    profile = user_res.get("response", {})
    email = profile.get("email")
    if not email:
        flash("네이버 로그인 정보(이메일)를 불러오는데 실패했습니다.", "error")
        return redirect(url_for("auth.login"))
    
    engine = current_app.extensions["db_engine"]
    with engine.begin() as conn:
        user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_email FROM tb_cs_member WHERE mbr_email = :email"), {"email": email}).fetchone()
        if not user:
            temp_name = f"naver_{profile.get('id', secrets.token_hex(4))[:8]}"
            conn.execute(text("INSERT INTO tb_cs_member (mbr_name, mbr_pwd, mbr_email, mbr_status) VALUES (:name, :pwd, :email, 'active')"),
                         {"name": temp_name, "pwd": "SOCIAL_LOGIN_NAVER", "email": email})
            user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_email FROM tb_cs_member WHERE mbr_email = :email"), {"email": email}).fetchone()
        session.update({"user_id": user[0], "username": user[1], "user_email": user[2]})
    return redirect(url_for("main.index"))

@auth_bp.route("/kakao/login")
def kakao_login():
    client_id = current_app.config.get("KAKAO_CLIENT_ID", "")
    redirect_uri = url_for("auth.kakao_callback", _external=True)
    auth_url = f"https://kauth.kakao.com/oauth/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
    return redirect(auth_url)

@auth_bp.route("/kakao/callback")
def kakao_callback():
    code = request.args.get("code")
    client_id = current_app.config.get("KAKAO_CLIENT_ID", "")
    redirect_uri = url_for("auth.kakao_callback", _external=True)
    
    token_res = requests.post("https://kauth.kakao.com/oauth/token", data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code
    }).json()
    
    user_res = requests.get("https://kapi.kakao.com/v2/user/me", headers={"Authorization": f"Bearer {token_res.get('access_token')}"}).json()
    kakao_account = user_res.get("kakao_account", {})
    email = kakao_account.get("email")
    
    if not email:
        flash("카카오 계정에 연결된 이메일이 없습니다.", "error")
        return redirect(url_for("auth.login"))
        
    engine = current_app.extensions["db_engine"]
    with engine.begin() as conn:
        user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_email FROM tb_cs_member WHERE mbr_email = :email"), {"email": email}).fetchone()
        if not user:
            temp_name = f"kakao_{str(user_res.get('id', secrets.token_hex(4)))[:8]}"
            conn.execute(text("INSERT INTO tb_cs_member (mbr_name, mbr_pwd, mbr_email, mbr_status) VALUES (:name, :pwd, :email, 'active')"),
                         {"name": temp_name, "pwd": "SOCIAL_LOGIN_KAKAO", "email": email})
            user = conn.execute(text("SELECT mbr_id, mbr_name, mbr_email FROM tb_cs_member WHERE mbr_email = :email"), {"email": email}).fetchone()
        session.update({"user_id": user[0], "username": user[1], "user_email": user[2]})
    return redirect(url_for("main.index"))
