from sqlalchemy import func, select

from app import db
from app.models import PAYMENT_STATUSES, Payment, Room, Student


def dormitory_stats():
    """Occupancy and payment totals shared by the dashboard and the API."""
    rooms, capacity = db.session.execute(
        select(func.count(Room.id), func.coalesce(func.sum(Room.capacity), 0))
    ).one()
    students, occupied = db.session.execute(
        select(func.count(Student.id), func.count(Student.room_id))
    ).one()

    payments = {}
    for status in PAYMENT_STATUSES:
        count, amount = db.session.execute(
            select(
                func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0)
            ).where(Payment.status_filter(status))
        ).one()
        payments[status] = {"count": count, "amount": float(amount)}

    return {
        "rooms": rooms,
        "capacity": int(capacity),
        "occupied": occupied,
        "free_places": max(int(capacity) - occupied, 0),
        "occupancy_percent": round(occupied * 100 / capacity) if capacity else 0,
        "students": students,
        "unassigned_students": students - occupied,
        "payments": payments,
    }
