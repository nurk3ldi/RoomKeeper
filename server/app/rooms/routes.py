from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import select

from app import db
from app.forms import RoomForm
from app.models import Room
from app.rooms import bp
from app.utils import admin_required, apply_sort, paginate

SORT_COLUMNS = {
    "number": Room.number,
    "floor": Room.floor,
    "capacity": Room.capacity,
    "occupied": Room.occupied,
    "price": Room.monthly_price,
}
AVAILABILITY_FILTERS = {
    "free": Room.occupied < Room.capacity,
    "full": Room.occupied >= Room.capacity,
    "empty": Room.occupied == 0,
}


@bp.get("/")
@login_required
def index():
    query = select(Room)

    q = request.args.get("q", "").strip()
    if q:
        query = query.where(Room.number.icontains(q, autoescape=True))

    floor = request.args.get("floor", type=int)
    if floor is not None:
        query = query.where(Room.floor == floor)

    availability = request.args.get("availability", "")
    if availability in AVAILABILITY_FILTERS:
        query = query.where(AVAILABILITY_FILTERS[availability])

    query, sort, order = apply_sort(query, SORT_COLUMNS, "number")
    floors = db.session.scalars(
        select(Room.floor).distinct().order_by(Room.floor)
    ).all()
    return render_template(
        "rooms/list.html",
        page=paginate(query.order_by(Room.id)),
        floors=floors,
        q=q,
        floor=floor,
        availability=availability,
        sort=sort,
        order=order,
    )


@bp.get("/<int:room_id>")
@login_required
def detail(room_id):
    room = db.get_or_404(Room, room_id)
    return render_template("rooms/detail.html", room=room)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    form = RoomForm()
    if form.validate_on_submit():
        room = Room()
        form.populate_obj(room)
        db.session.add(room)
        db.session.commit()
        flash(f"№{room.number} бөлме қосылды.", "success")
        return redirect(url_for("rooms.detail", room_id=room.id))
    return render_template("rooms/form.html", form=form, room=None)


@bp.route("/<int:room_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(room_id):
    room = db.get_or_404(Room, room_id)
    form = RoomForm(obj=room)
    if form.validate_on_submit():
        form.populate_obj(room)
        db.session.commit()
        flash(f"№{room.number} бөлме жаңартылды.", "success")
        return redirect(url_for("rooms.detail", room_id=room.id))
    return render_template("rooms/form.html", form=form, room=room)


@bp.post("/<int:room_id>/delete")
@admin_required
def delete(room_id):
    room = db.get_or_404(Room, room_id)
    if room.occupied:
        flash(
            f"№{room.number} бөлмеде студенттер тұрады — алдымен оларды көшіріңіз.",
            "danger",
        )
        return redirect(url_for("rooms.detail", room_id=room.id))
    number = room.number
    db.session.delete(room)
    db.session.commit()
    flash(f"№{number} бөлме өшірілді.", "success")
    return redirect(url_for("rooms.index"))
