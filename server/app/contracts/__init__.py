from flask import Blueprint

bp = Blueprint("contracts", __name__)

from app.contracts import routes  # noqa: E402,F401
