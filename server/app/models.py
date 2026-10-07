from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import column_property
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager

ROLE_ADMIN = "admin"
ROLE_USER = "user"

STATUS_PAID = "paid"
STATUS_PENDING = "pending"
STATUS_OVERDUE = "overdue"
PAYMENT_STATUSES = (STATUS_PAID, STATUS_PENDING, STATUS_OVERDUE)


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default=ROLE_USER)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    student = db.relationship("Student", back_populates="user", uselist=False)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @classmethod
    def authenticate(cls, login, password):
        """Return the user matching a username or email and password."""
        login = login.strip().lower()
        user = db.session.scalar(
            select(cls).where(
                or_(func.lower(cls.username) == login, cls.email == login)
            )
        )
        if user is not None and user.check_password(password):
            return user
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
        }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Unknown for students who signed up themselves, until an admin
    # fills them in.
    phone = db.Column(db.String(20))
    course = db.Column(db.Integer)
    room_id = db.Column(
        db.Integer, db.ForeignKey("rooms.id", ondelete="SET NULL"), index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    room = db.relationship("Room", back_populates="students")
    user = db.relationship("User", back_populates="student")
    contracts = db.relationship(
        "Contract",
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="Contract.start_date.desc()",
    )

    @classmethod
    def find_by_email(cls, email):
        return db.session.scalar(
            select(cls).where(func.lower(cls.email) == email.lower())
        )

    @classmethod
    def link_account(cls, user, full_name):
        """Give a newly registered account its student record.

        A record an admin already entered under the same email is reused
        (and keeps the admin's spelling of the name); otherwise a new one
        is created.
        """
        student = cls.find_by_email(user.email)
        if student is None:
            student = cls(full_name=full_name, email=user.email)
            db.session.add(student)
        student.user = user
        return student

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "course": self.course,
            "room_id": self.room_id,
            "room_number": self.room.number if self.room else None,
        }


class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(10), unique=True, nullable=False)
    floor = db.Column(db.Integer, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    monthly_price = db.Column(db.Numeric(10, 2), nullable=False)

    students = db.relationship(
        "Student", back_populates="room", order_by="Student.full_name"
    )

    # Computed in SQL so lists can filter and sort by occupancy without
    # loading every student.
    occupied = column_property(
        select(func.count(Student.id))
        .where(Student.room_id == id)
        .correlate_except(Student)
        .scalar_subquery()
    )

    @property
    def free_places(self):
        return max(self.capacity - self.occupied, 0)

    @property
    def is_full(self):
        return self.occupied >= self.capacity

    @property
    def occupancy_percent(self):
        if not self.capacity:
            return 0
        return round(self.occupied * 100 / self.capacity)

    def to_dict(self):
        return {
            "id": self.id,
            "number": self.number,
            "floor": self.floor,
            "capacity": self.capacity,
            "monthly_price": float(self.monthly_price),
            "occupied": self.occupied,
            "free_places": self.free_places,
            "occupancy_percent": self.occupancy_percent,
        }


class Contract(db.Model):
    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(30), unique=True, nullable=False)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    monthly_fee = db.Column(db.Numeric(10, 2), nullable=False)
    # pdf_filename is the random name on disk; pdf_original_name is the
    # sanitised name offered to the browser on download.
    pdf_filename = db.Column(db.String(64))
    pdf_original_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    student = db.relationship("Student", back_populates="contracts")
    payments = db.relationship(
        "Payment",
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="Payment.due_date",
    )

    @property
    def state(self):
        today = date.today()
        if today < self.start_date:
            return "upcoming"
        if today > self.end_date:
            return "expired"
        return "active"

    @classmethod
    def state_filter(cls, state):
        today = date.today()
        if state == "upcoming":
            return cls.start_date > today
        if state == "expired":
            return cls.end_date < today
        return and_(cls.start_date <= today, cls.end_date >= today)

    @property
    def total_due(self):
        return sum((p.amount for p in self.payments), Decimal("0"))

    @property
    def total_paid(self):
        return sum((p.amount for p in self.payments if p.is_paid), Decimal("0"))

    @property
    def debt(self):
        """Unpaid amount whose due date has already passed."""
        return sum(
            (p.amount for p in self.payments if p.status == STATUS_OVERDUE),
            Decimal("0"),
        )

    def build_schedule(self):
        """One payment per month of the contract, due on the start day."""
        payments = []
        year, month = self.start_date.year, self.start_date.month
        while True:
            day = min(self.start_date.day, monthrange(year, month)[1])
            due = date(year, month, day)
            if due > self.end_date:
                break
            payments.append(Payment(amount=self.monthly_fee, due_date=due))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return payments

    def to_dict(self):
        return {
            "id": self.id,
            "number": self.number,
            "student_id": self.student_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "monthly_fee": float(self.monthly_fee),
            "state": self.state,
            "has_pdf": bool(self.pdf_filename),
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(
        db.Integer,
        db.ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False, index=True)
    paid_at = db.Column(db.Date)
    comment = db.Column(db.String(200))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    contract = db.relationship("Contract", back_populates="payments")

    @property
    def is_paid(self):
        return self.paid_at is not None

    @property
    def status(self):
        if self.is_paid:
            return STATUS_PAID
        if self.due_date < date.today():
            return STATUS_OVERDUE
        return STATUS_PENDING

    @classmethod
    def status_filter(cls, status):
        """SQL counterpart of the `status` property."""
        today = date.today()
        if status == STATUS_PAID:
            return cls.paid_at.is_not(None)
        if status == STATUS_OVERDUE:
            return and_(cls.paid_at.is_(None), cls.due_date < today)
        return and_(cls.paid_at.is_(None), cls.due_date >= today)

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "contract_number": self.contract.number,
            "student": self.contract.student.full_name,
            "amount": float(self.amount),
            "due_date": self.due_date.isoformat(),
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "status": self.status,
        }
