from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def init_db(app: Flask) -> None:
    app.extensions["db_engine"] = create_engine(
        app.config["SQLALCHEMY_DATABASE_URI"],
        pool_pre_ping=True,
        future=True,
    )

    @app.get("/health")
    def healthcheck():
        try:
            with app.extensions["db_engine"].connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ok", "database": "connected"}, 200
        except SQLAlchemyError:
            return {"status": "degraded", "database": "disconnected"}, 503
