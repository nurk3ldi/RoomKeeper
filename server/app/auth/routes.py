from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.auth import bp
from app.forms import LoginForm, RegisterForm
from app.models import User
from app.utils import safe_next_url


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.authenticate(form.login.data, form.password.data)
        if user is not None:
            login_user(user)
            flash(f"Қош келдіңіз, {user.username}!", "success")
            return redirect(safe_next_url(url_for("main.dashboard")))
        flash("Логин немесе құпиясөз қате.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Тіркелу сәтті өтті. Енді жүйеге кіріңіз.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Жүйеден шықтыңыз.", "info")
    return redirect(url_for("main.home"))
