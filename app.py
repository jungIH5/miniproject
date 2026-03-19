from dotenv import load_dotenv

# override=True를 주어야 서버 재시작 시 새롭게 바꾼 .env 값을 강제로 덮어씌웁니다.
load_dotenv(override=True)

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
