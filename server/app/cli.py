from datetime import date
from decimal import Decimal

import click
from sqlalchemy import func, select

from app import db
from app.models import ROLE_ADMIN, Contract, Room, Student, User

DEMO_ADMIN = ("admin", "admin@roomkeeper.kz", "Admin123!")
DEMO_USERS = [
    ("aigerim", "aigerim@roomkeeper.kz", "User123!"),
    ("daulet", "daulet@roomkeeper.kz", "User123!"),
]
# Monthly price by room capacity.
DEMO_PRICES = {2: Decimal("35000"), 3: Decimal("28000"), 4: Decimal("22000")}
DEMO_UNASSIGNED = 4
DEMO_STUDENTS = [
    "Айгерім Сейітқызы",
    "Нұрлан Әбдіқадыров",
    "Дана Жұмабекова",
    "Ерлан Тоқтаров",
    "Мадина Оспанова",
    "Арман Қасымов",
    "Жанар Мұратқызы",
    "Бекзат Серікұлы",
    "Аружан Нұрланқызы",
    "Темірлан Ахметов",
    "Гүлназ Ибраева",
    "Санжар Әлиев",
    "Камила Досжанова",
    "Олжас Байжанов",
    "Айдана Қуанышева",
    "Ерасыл Мұхамеджанов",
    "Динара Сағынтаева",
    "Алихан Жақсыбеков",
    "Томирис Есенова",
    "Нұрсұлтан Қалиев",
    "Асель Тұрсынова",
    "Дәурен Садықов",
    "Меруерт Бекова",
    "Рүстем Ысқақов",
    "Зарина Әмірова",
    "Абылай Жүнісов",
]


def create_demo_data():
    admin = User(username=DEMO_ADMIN[0], email=DEMO_ADMIN[1], role=ROLE_ADMIN)
    admin.set_password(DEMO_ADMIN[2])
    users = [admin]
    for username, email, password in DEMO_USERS:
        user = User(username=username, email=email)
        user.set_password(password)
        users.append(user)
    db.session.add_all(users)

    rooms = []
    for floor in (1, 2, 3):
        for index in range(1, 5):
            capacity = 2 + (floor + index) % 3
            rooms.append(
                Room(
                    number=f"{floor}{index:02d}",
                    floor=floor,
                    capacity=capacity,
                    monthly_price=DEMO_PRICES[capacity],
                )
            )
    db.session.add_all(rooms)

    # Hand out places one per room in turn. The last room stays empty and
    # the last few students stay unassigned, so the demo has full, partly
    # filled and empty rooms as well as students without a room.
    places = [
        room
        for slot in range(max(DEMO_PRICES))
        for room in rooms[:-1]
        if slot < room.capacity
    ]
    housed = len(DEMO_STUDENTS) - DEMO_UNASSIGNED
    today = date.today()
    year = today.year if today.month >= 9 else today.year - 1
    start, end = date(year, 9, 1), date(year + 1, 6, 30)

    for index, name in enumerate(DEMO_STUDENTS):
        room = places[index] if index < housed else None
        student = Student(
            full_name=name,
            email=f"student{index + 1:02d}@example.kz",
            phone=f"+7701{1000000 + index * 7919:07d}",
            course=1 + index % 4,
            room=room,
            user=users[1] if index == 0 else None,
        )
        db.session.add(student)
        if room is None:
            continue

        contract = Contract(
            student=student,
            number=f"RK-{year}-{index + 1:03d}",
            start_date=start,
            end_date=end,
            monthly_fee=room.monthly_price,
        )
        contract.payments = contract.build_schedule()
        db.session.add(contract)
        # Every fourth student is behind on the most recent payment.
        due_so_far = [p for p in contract.payments if p.due_date <= today]
        unpaid = due_so_far[-1:] if index % 4 == 3 else []
        for payment in due_so_far:
            if payment not in unpaid:
                payment.paid_at = payment.due_date

    db.session.commit()


def register(app):
    @app.cli.command("init-db")
    @click.option("--drop", is_flag=True, help="Drop all tables first (deletes data).")
    def init_db(drop):
        """Create the database tables."""
        if drop:
            click.confirm("This deletes ALL data. Continue?", abort=True)
            db.drop_all()
        db.create_all()
        click.echo("Database tables are ready.")

    @app.cli.command("seed")
    def seed():
        """Fill an empty database with demo accounts and data."""
        if db.session.scalar(select(func.count(User.id))):
            raise click.ClickException(
                "The database already has users. Run `init-db --drop` first."
            )
        create_demo_data()
        click.echo(f"Demo data created. Admin: {DEMO_ADMIN[0]} / {DEMO_ADMIN[2]}")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(username, email, password):
        """Create an administrator account."""
        taken = db.session.scalar(
            select(User).where(
                (func.lower(User.username) == username.lower())
                | (User.email == email.lower())
            )
        )
        if taken is not None:
            raise click.ClickException("Username or email is already taken.")
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters.")
        user = User(username=username, email=email.lower(), role=ROLE_ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin {username} created.")
