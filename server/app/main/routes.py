from flask import render_template
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app import db
from app.main import bp
from app.models import STATUS_OVERDUE, Contract, Payment, Room
from app.services import dormitory_stats

DASHBOARD_ROWS = 5


@bp.get("/")
@login_required
def dashboard():
    free_rooms = db.session.scalars(
        select(Room)
        .where(Room.occupied < Room.capacity)
        .order_by(Room.number)
        .limit(DASHBOARD_ROWS)
    ).all()

    overdue = []
    if current_user.is_admin:
        overdue = db.session.scalars(
            select(Payment)
            .where(Payment.status_filter(STATUS_OVERDUE))
            .options(joinedload(Payment.contract).joinedload(Contract.student))
            .order_by(Payment.due_date)
            .limit(DASHBOARD_ROWS)
        ).all()

    return render_template(
        "main/dashboard.html",
        stats=dormitory_stats(),
        free_rooms=free_rooms,
        overdue=overdue,
    )


@bp.get("/profile")
@login_required
def profile():
    return render_template("main/profile.html", student=current_user.student)
