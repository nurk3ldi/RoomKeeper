from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    @app.get("/api/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "db": "ok"}

    return app
