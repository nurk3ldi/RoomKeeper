from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from app import db, login_manager

ERROR_PAGES = {403, 404, 413, 500}


def wants_json():
    return request.path.startswith("/api/")


def error_response(code, name, description=None):
    if wants_json():
        return jsonify(error=name, message=description, status=code), code
    template = f"errors/{code}.html" if code in ERROR_PAGES else "errors/layout.html"
    return render_template(template, code=code, title=name, text=description), code


def register(app):
    @app.errorhandler(HTTPException)
    def http_error(error):
        return error_response(error.code, error.name, error.description)

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return error_response(
            400,
            "Сессия мерзімі өтті",
            "Қауіпсіздік токені жарамсыз. Бетті жаңартып, қайталап көріңіз.",
        )

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return error_response(500, "Internal Server Error")

    @login_manager.unauthorized_handler
    def unauthorized():
        if wants_json():
            return error_response(401, "Unauthorized", "Login required.")
        flash("Бұл бетті ашу үшін жүйеге кіріңіз.", "warning")
        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for("auth.login", next=next_url))
