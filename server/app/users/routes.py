from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app import db
from app.models import ROLE_ADMIN, ROLE_USER, Student, User
from app.template_helpers import ROLE_LABELS
from app.users import bp
from app.utils import admin_required, paginate


def get_other_user(user_id):
    """Load a user, refusing actions an admin aims at their own account.

    This keeps at least one admin in the system at all times.
    """
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Өз аккаунтыңызды бұл жерден өзгерте алмайсыз.", "danger")
        return None
    return user


@bp.get("/")
@admin_required
def index():
    query = select(User).options(joinedload(User.student))

    q = request.args.get("q", "").strip()
    if q:
        query = query.where(
            or_(
                User.username.icontains(q, autoescape=True),
                User.email.icontains(q, autoescape=True),
            )
        )

    role = request.args.get("role", "")
    if role in ROLE_LABELS:
        query = query.where(User.role == role)

    return render_template(
        "users/list.html",
        page=paginate(query.order_by(User.username)),
        q=q,
        role=role,
    )


@bp.post("/<int:user_id>/role")
@admin_required
def toggle_role(user_id):
    user = get_other_user(user_id)
    if user is not None:
        user.role = ROLE_USER if user.is_admin else ROLE_ADMIN
        if not user.is_admin and user.student is None:
            # Every non-admin account is a student's account.
            Student.link_account(user, user.username)
        db.session.commit()
        flash(f"{user.username} рөлі: {ROLE_LABELS[user.role]}.", "success")
    return redirect(url_for("users.index"))


@bp.post("/<int:user_id>/delete")
@admin_required
def delete(user_id):
    user = get_other_user(user_id)
    if user is not None:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f"{username} аккаунты өшірілді.", "success")
    return redirect(url_for("users.index"))
