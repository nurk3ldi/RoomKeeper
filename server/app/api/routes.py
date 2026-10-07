from flask import abort, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_, select
from sqlalchemy.orm import contains_eager, joinedload
from werkzeug.datastructures import MultiDict

from app import db
from app.api import bp
from app.forms import RoomForm
from app.models import PAYMENT_STATUSES, Contract, Payment, Room, Student, User
from app.services import dormitory_stats
from app.utils import admin_required, paginate

ROOM_FIELDS = ("number", "floor", "capacity", "monthly_price")


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Request body must be a JSON object.")
    return data


def page_payload(page):
    return {
        "items": [item.to_dict() for item in page.items],
        "page": page.page,
        "pages": page.pages,
        "per_page": page.per_page,
        "total": page.total,
    }


def validation_error(form):
    return jsonify(error="Validation failed", fields=form.errors, status=400), 400


def room_form(payload, room=None):
    """Validate room JSON with the same form the HTML pages use.

    Fields missing from the payload keep the room's current values, so PUT
    also accepts partial updates.
    """
    data = {name: getattr(room, name) for name in ROOM_FIELDS} if room else {}
    data.update({k: v for k, v in payload.items() if k in ROOM_FIELDS})
    formdata = MultiDict({k: str(v) for k, v in data.items() if v is not None})
    return RoomForm(formdata=formdata, obj=room, meta={"csrf": False})


@bp.get("/health")
def health():
    db.session.execute(db.text("SELECT 1"))
    return {"status": "ok", "db": "ok"}


@bp.post("/auth/login")
def login():
    data = json_body()
    user = User.authenticate(str(data.get("login", "")), str(data.get("password", "")))
    if user is None:
        abort(401, description="Invalid login or password.")
    login_user(user)
    return {"user": user.to_dict()}


@bp.post("/auth/logout")
@login_required
def logout():
    logout_user()
    return {"status": "ok"}


@bp.get("/auth/me")
@login_required
def me():
    return {"user": current_user.to_dict()}


@bp.get("/stats")
@login_required
def stats():
    return dormitory_stats()


@bp.get("/rooms")
@login_required
def list_rooms():
    query = select(Room)
    floor = request.args.get("floor", type=int)
    if floor is not None:
        query = query.where(Room.floor == floor)
    if request.args.get("available") == "1":
        query = query.where(Room.occupied < Room.capacity)
    return page_payload(paginate(query.order_by(Room.number, Room.id)))


@bp.get("/rooms/<int:room_id>")
@login_required
def get_room(room_id):
    return db.get_or_404(Room, room_id).to_dict()


@bp.post("/rooms")
@admin_required
def create_room():
    form = room_form(json_body())
    if not form.validate():
        return validation_error(form)
    room = Room()
    form.populate_obj(room)
    db.session.add(room)
    db.session.commit()
    return room.to_dict(), 201


@bp.put("/rooms/<int:room_id>")
@admin_required
def update_room(room_id):
    room = db.get_or_404(Room, room_id)
    form = room_form(json_body(), room)
    if not form.validate():
        return validation_error(form)
    form.populate_obj(room)
    db.session.commit()
    return room.to_dict()


@bp.delete("/rooms/<int:room_id>")
@admin_required
def delete_room(room_id):
    room = db.get_or_404(Room, room_id)
    if room.occupied:
        abort(409, description="Room still has students assigned.")
    db.session.delete(room)
    db.session.commit()
    return "", 204


@bp.get("/students")
@admin_required
def list_students():
    query = select(Student).options(joinedload(Student.room))
    q = request.args.get("q", "").strip()
    if q:
        query = query.where(
            or_(
                Student.full_name.icontains(q, autoescape=True),
                Student.email.icontains(q, autoescape=True),
            )
        )
    room_id = request.args.get("room_id", type=int)
    if room_id is not None:
        query = query.where(Student.room_id == room_id)
    return page_payload(paginate(query.order_by(Student.full_name, Student.id)))


@bp.get("/payments")
@admin_required
def list_payments():
    query = (
        select(Payment)
        .join(Payment.contract)
        .join(Contract.student)
        .options(contains_eager(Payment.contract).contains_eager(Contract.student))
    )
    status = request.args.get("status", "")
    if status:
        if status not in PAYMENT_STATUSES:
            abort(400, description=f"status must be one of {list(PAYMENT_STATUSES)}.")
        query = query.where(Payment.status_filter(status))
    return page_payload(paginate(query.order_by(Payment.due_date, Payment.id)))
