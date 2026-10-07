import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Built-in WTForms messages (e.g. "not a valid integer") come from the
    # form's own locale list instead of Flask-Babel.
    WTF_I18N_ENABLED = False

    # Contract PDFs live outside static/ so they are only served through
    # an access-checked view.
    UPLOAD_FOLDER = BASE_DIR / "uploads" / "contracts"
    ALLOWED_UPLOAD_EXTENSIONS = {"pdf"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    ITEMS_PER_PAGE = 10
