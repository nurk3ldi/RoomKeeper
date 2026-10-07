import os
from datetime import date, timedelta
from decimal import Decimal

# config.py reads these at import time; tests never touch the real database.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models import ROLE_ADMIN, ROLE_USER, Contract, Payment, Room, Student, User  # noqa: E402
from config import Config  # noqa: E402

PASSWORD = "Password123"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    ITEMS_PER_PAGE = 5


@pytest.fixture
def app(tmp_path):
    app = create_app(TestConfig)
    app.config["UPLOAD_FOLDER"] = tmp_path / "uploads"
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


class Factory:
    """Create rows in their own app context and hand back plain ids.

    Tests must not hold an app context open across client requests:
    Flask-Login caches the current user on `g`, which would leak between
    requests.
    """

    def __init__(self, app):
        self.app = app
        self.counter = 0

    def _add(self, obj):
        with self.app.app_context():
            db.session.add(obj)
            db.session.commit()
            return obj.id

    def _next(self):
        self.counter += 1
        return self.counter

    def user(self, username="user", role=ROLE_USER):
        user = User(username=username, email=f"{username}@example.com", role=role)
        user.set_password(PASSWORD)
        return self._add(user)

    def room(self, number=None, floor=1, capacity=2, price="30000"):
        number = number or f"R{self._next()}"
        return self._add(
            Room(number=number, floor=floor, capacity=capacity, monthly_price=Decimal(price))
        )

    def student(self, name=None, room_id=None, user_id=None, course=1):
        n = self._next()
        return self._add(
            Student(
                full_name=name or f"Student {n}",
                email=f"student{n}@example.com",
                phone=f"+7701000{n:04d}",
                course=course,
                room_id=room_id,
                user_id=user_id,
            )
        )

    def contract(self, student_id, number=None, start=None, end=None, fee="30000"):
        start = start or date.today() - timedelta(days=30)
        return self._add(
            Contract(
                student_id=student_id,
                number=number or f"C-{self._next()}",
                start_date=start,
                end_date=end or start + timedelta(days=300),
                monthly_fee=Decimal(fee),
            )
        )

    def payment(self, contract_id, due_in_days=10, paid=False, amount="30000"):
        due = date.today() + timedelta(days=due_in_days)
        return self._add(
            Payment(
                contract_id=contract_id,
                amount=Decimal(amount),
                due_date=due,
                paid_at=min(due, date.today()) if paid else None,
            )
        )


@pytest.fixture
def make(app):
    return Factory(app)


def login(client, username):
    return client.post("/auth/login", data={"login": username, "password": PASSWORD})


@pytest.fixture
def admin_client(app, make):
    make.user("admin", ROLE_ADMIN)
    client = app.test_client()
    login(client, "admin")
    return client


@pytest.fixture
def user_client(app, make):
    make.user("user")
    client = app.test_client()
    login(client, "user")
    return client


@pytest.fixture
def query(app):
    """Run a read against the database outside of any request."""

    def run(fn):
        with app.app_context():
            return fn()

    return run
