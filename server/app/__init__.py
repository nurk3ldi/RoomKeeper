from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app import models  # noqa: F401  (registers tables and the user loader)
    from app.api import bp as api_bp
    from app.auth import bp as auth_bp
    from app.contracts import bp as contracts_bp
    from app.main import bp as main_bp
    from app.payments import bp as payments_bp
    from app.rooms import bp as rooms_bp
    from app.students import bp as students_bp
    from app.users import bp as users_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(rooms_bp, url_prefix="/rooms")
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(contracts_bp, url_prefix="/contracts")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(api_bp, url_prefix="/api")

    # The JSON API has no form to carry a CSRF token; it relies on the
    # SameSite=Lax session cookie and JSON-only request bodies instead.
    csrf.exempt(api_bp)

    from app import cli, errors, template_helpers

    errors.register(app)
    cli.register(app)
    template_helpers.register(app)

    return app
