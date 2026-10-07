from flask import Blueprint

bp = Blueprint("students", __name__)

from app.students import routes  # noqa: E402,F401
