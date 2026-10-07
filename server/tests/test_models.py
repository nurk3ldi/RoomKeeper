from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app import db
from app.models import PAYMENT_STATUSES, Contract, Payment, Room
from app.services import dormitory_stats


def test_room_occupancy_is_calculated_from_students(app, make):
    room_id = make.room(capacity=2)
    make.student(room_id=room_id)

    with app.app_context():
        room = db.session.get(Room, room_id)
        assert (room.occupied, room.free_places, room.occupancy_percent) == (1, 1, 50)
        assert not room.is_full

    make.student(room_id=room_id)
    with app.app_context():
        room = db.session.get(Room, room_id)
        assert (room.occupied, room.free_places, room.occupancy_percent) == (2, 0, 100)
        assert room.is_full


def test_payment_status_property_matches_sql_filter(app, make):
    contract_id = make.contract(make.student())
    paid = make.payment(contract_id, due_in_days=-5, paid=True)
    pending = make.payment(contract_id, due_in_days=5)
    due_today = make.payment(contract_id, due_in_days=0)
    overdue = make.payment(contract_id, due_in_days=-1)

    with app.app_context():
        by_status = {
            status: set(
                db.session.scalars(
                    select(Payment.id).where(Payment.status_filter(status))
                )
            )
            for status in PAYMENT_STATUSES
        }
        assert by_status == {
            "paid": {paid},
            "pending": {pending, due_today},
            "overdue": {overdue},
        }
        for status, ids in by_status.items():
            for payment_id in ids:
                assert db.session.get(Payment, payment_id).status == status


def test_schedule_has_one_payment_per_month():
    contract = Contract(
        start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), monthly_fee=Decimal("25000")
    )
    schedule = contract.build_schedule()

    assert len(schedule) == 10
    assert schedule[0].due_date == date(2026, 9, 1)
    assert schedule[-1].due_date == date(2027, 6, 1)
    assert {p.amount for p in schedule} == {Decimal("25000")}


def test_schedule_clamps_day_to_short_months():
    contract = Contract(
        start_date=date(2027, 1, 31), end_date=date(2027, 4, 30), monthly_fee=Decimal("1")
    )
    assert [p.due_date for p in contract.build_schedule()] == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
        date(2027, 4, 30),
    ]


def test_contract_totals_and_debt(app, make):
    contract_id = make.contract(make.student())
    make.payment(contract_id, due_in_days=-40, paid=True, amount="100")
    make.payment(contract_id, due_in_days=-10, amount="200")
    make.payment(contract_id, due_in_days=20, amount="400")

    with app.app_context():
        contract = db.session.get(Contract, contract_id)
        assert contract.total_due == Decimal("700")
        assert contract.total_paid == Decimal("100")
        assert contract.debt == Decimal("200")


def test_contract_state(app, make):
    student_id = make.student()
    today = date.today()
    ids = {
        "active": make.contract(student_id, start=today - timedelta(days=1), end=today + timedelta(days=1)),
        "upcoming": make.contract(student_id, start=today + timedelta(days=1), end=today + timedelta(days=9)),
        "expired": make.contract(student_id, start=today - timedelta(days=9), end=today - timedelta(days=1)),
    }
    with app.app_context():
        for state, contract_id in ids.items():
            assert db.session.get(Contract, contract_id).state == state
            assert db.session.scalars(
                select(Contract.id).where(Contract.state_filter(state))
            ).all() == [contract_id]


def test_dormitory_stats(app, make):
    full = make.room(capacity=1)
    make.room(capacity=3)
    contract_id = make.contract(make.student(room_id=full))
    make.student()
    make.payment(contract_id, due_in_days=-3, amount="500")
    make.payment(contract_id, due_in_days=-3, paid=True, amount="700")

    with app.app_context():
        stats = dormitory_stats()

    assert stats["rooms"] == 2
    assert (stats["capacity"], stats["occupied"], stats["free_places"]) == (4, 1, 3)
    assert stats["occupancy_percent"] == 25
    assert (stats["students"], stats["unassigned_students"]) == (2, 1)
    assert stats["payments"]["overdue"] == {"count": 1, "amount": 500.0}
    assert stats["payments"]["paid"] == {"count": 1, "amount": 700.0}
    assert stats["payments"]["pending"] == {"count": 0, "amount": 0.0}


def test_stats_on_empty_database(app):
    with app.app_context():
        stats = dormitory_stats()
        assert db.session.scalar(select(func.count(Room.id))) == 0
    assert stats["occupancy_percent"] == 0
    assert stats["free_places"] == 0
