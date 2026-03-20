import requests
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

main_blueprint = Blueprint("main", __name__)

# 네이버 OAuth 설정
NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USERINFO_URL = "https://openapi.naver.com/v1/nid/me"

@main_blueprint.get("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("main.login"))
    return render_template("index.html")

@main_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mbr_name = request.form.get("username")
        mbr_pwd = request.form.get("password")
        
        engine = current_app.extensions["db_engine"]
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT mbr_id, mbr_name, mbr_pwd FROM tb_cs_members WHERE mbr_name = :name"),
                {"name": mbr_name}
            ).fetchone()
            
            if result and check_password_hash(result[2], mbr_pwd):
                session["user_id"] = result[0]
                session["username"] = result[1]
                return redirect(url_for("main.index"))
            else:
                flash("아이디 또는 비밀번호가 일치하지 않습니다.", "error")
                
    return render_template("login.html")

# --- 네이버 로그인 시작 ---
@main_blueprint.get("/naver/login")
def naver_login():
    state = secrets.token_urlsafe(16)
    session["naver_state"] = state
    client_id = current_app.config["NAVER_LOGIN_ID"]
    callback_url = url_for("main.naver_callback", _external=True)
    auth_url = f"{NAVER_AUTH_URL}?response_type=code&client_id={client_id}&redirect_uri={callback_url}&state={state}"
    return redirect(auth_url)

@main_blueprint.route("/naver/callback")
def naver_callback():
    code, state = request.args.get("code"), request.args.get("state")
    if state != session.get("naver_state"):
        flash("세션이 만료되었습니다.", "error")
        return redirect(url_for("main.login"))

    # 토큰 및 프로필 요청 (네이버)
    token_res = requests.post(NAVER_TOKEN_URL, data={
        "grant_type": "authorization_code", "client_id": current_app.config["NAVER_LOGIN_ID"],
        "client_secret": current_app.config["NAVER_LOGIN_SECRET"], "code": code, "state": state
    }).json()
    
    user_res = requests.get(NAVER_USERINFO_URL, headers={"Authorization": f"Bearer {token_res.get('access_token')}"}).json()
    profile = user_res.get("response")
    email = profile.get("email")
    
    engine = current_app.extensions["db_engine"]
    with engine.begin() as conn:
        user = conn.execute(text("SELECT mbr_id, mbr_name FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        if not user:
            temp_name = f"naver_{profile.get('id')[:8]}"
            conn.execute(text("INSERT INTO tb_cs_members (mbr_name, mbr_pwd, mbr_email, mbr_status) VALUES (:name, :pwd, :email, 'active')"),
                         {"name": temp_name, "pwd": "SOCIAL_LOGIN_NAVER", "email": email})
            user = conn.execute(text("SELECT mbr_id, mbr_name FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        session["user_id"], session["username"] = user[0], user[1]
    return redirect(url_for("main.index"))

# --- 구글 로그인 시작 ---
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

@main_blueprint.get("/google/login")
def google_login():
    state = secrets.token_urlsafe(16)
    session["google_state"] = state
    client_id = current_app.config["GOOGLE_CLIENT_ID"]
    callback_url = url_for("main.google_callback", _external=True)
    auth_url = f"{GOOGLE_AUTH_URL}?response_type=code&client_id={client_id}&redirect_uri={callback_url}&scope=openid email profile&state={state}"
    return redirect(auth_url)

@main_blueprint.route("/google/callback")
def google_callback():
    code, state = request.args.get("code"), request.args.get("state")
    if state != session.get("google_state"):
        flash("세션이 만료되었습니다.", "error")
        return redirect(url_for("main.login"))

    token_res = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code, "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": url_for("main.google_callback", _external=True), "grant_type": "authorization_code"
    }).json()

    user_res = requests.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {token_res.get('access_token')}"}).json()
    email = user_res.get("email")
    
    engine = current_app.extensions["db_engine"]
    with engine.begin() as conn:
        user = conn.execute(text("SELECT mbr_id, mbr_name FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        if not user:
            temp_name = f"google_{user_res.get('sub')[:8]}"
            conn.execute(text("INSERT INTO tb_cs_members (mbr_name, mbr_pwd, mbr_email, mbr_status) VALUES (:name, :pwd, :email, 'active')"),
                         {"name": temp_name, "pwd": "SOCIAL_LOGIN_GOOGLE", "email": email})
            user = conn.execute(text("SELECT mbr_id, mbr_name FROM tb_cs_members WHERE field = :email"), {"email": email}).fetchone() # fix table check
            user = conn.execute(text("SELECT mbr_id, mbr_name FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        session["user_id"], session["username"] = user[0], user[1]
    return redirect(url_for("main.index"))

# --- 카카오 로그인 시작 ---
KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

@main_blueprint.get("/kakao/login")
def kakao_login():
    client_id = current_app.config["KAKAO_CLIENT_ID"]
    callback_url = url_for("main.kakao_callback", _external=True)
    auth_url = f"{KAKAO_AUTH_URL}?client_id={client_id}&redirect_uri={callback_url}&response_type=code"
    return redirect(auth_url)

@main_blueprint.route("/kakao/callback")
def kakao_callback():
    code = request.args.get("code")
    token_res = requests.post(KAKAO_TOKEN_URL, data={
        "grant_type": "authorization_code", "client_id": current_app.config["KAKAO_CLIENT_ID"],
        "client_secret": current_app.config["KAKAO_CLIENT_SECRET"],
        "redirect_uri": url_for("main.kakao_callback", _external=True), "code": code
    }).json()

    user_res = requests.get(KAKAO_USERINFO_URL, headers={"Authorization": f"Bearer {token_res.get('access_token')}"}).json()
    kakao_account = user_res.get("kakao_account")
    email = kakao_account.get("email", f"{user_res.get('id')}@kakao.com")
    
    engine = current_app.extensions["db_engine"]
    with engine.begin() as conn:
        user = conn.execute(text("SELECT mbr_id, mbr_name FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        if not user:
            temp_name = f"kakao_{user_res.get('id')}"
            conn.execute(text("INSERT INTO tb_cs_members (mbr_name, mbr_pwd, mbr_email, mbr_status) VALUES (:name, :pwd, :email, 'active')"),
                         {"name": temp_name, "pwd": "SOCIAL_LOGIN_KAKAO", "email": email})
            user = conn.execute(text("SELECT mbr_id, mbr_name FROM tb_cs_members WHERE mbr_email = :email"), {"email": email}).fetchone()
        session["user_id"], session["username"] = user[0], user[1]
    return redirect(url_for("main.index"))

@main_blueprint.route("/signup", methods=["GET", "POST"])
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
                    text("SELECT 1 FROM tb_cs_members WHERE mbr_name = :name"),
                    {"name": mbr_name}
                ).fetchone()
                
                if existing:
                    flash("이미 존재하는 아이디입니다.", "error")
                else:
                    conn.execute(
                        text("""
                            INSERT INTO tb_cs_members (mbr_name, mbr_pwd, mbr_email, mbr_status)
                            VALUES (:name, :pwd, :email, 'active')
                        """),
                        {"name": mbr_name, "pwd": hashed_pwd, "email": mbr_email}
                    )
                    flash("회원가입이 완료되었습니다! 로그인해주세요.", "success")
                    return redirect(url_for("main.login"))
        except Exception as e:
            flash(f"가입 중 오류가 발생했습니다: {e}", "error")
    return render_template("signup.html")

@main_blueprint.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))
