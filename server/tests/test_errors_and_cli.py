from sqlalchemy import func, select

from app import db
from app.models import Contract, Payment, Room, Student, User


def test_custom_404_page(client):
    response = client.get("/no/such/page")
    html = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Бет табылмады" in html and "Басты бетке оралу" in html
    assert response.mimetype == "text/html"


def test_custom_500_page_and_rollback(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/boom")
    def boom():
        db.session.add(Room(number="X", floor=1, capacity=1, monthly_price=1))
        db.session.flush()
        raise RuntimeError("boom")

    response = client.get("/boom")
    assert response.status_code == 500
    assert "Серверде қате орын алды" in response.get_data(as_text=True)
    assert "RuntimeError" not in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(func.count(Room.id))) == 0


def test_500_from_api_is_json(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/api/boom")
    def api_boom():
        raise RuntimeError("boom")

    response = client.get("/api/boom")
    assert response.status_code == 500
    assert response.get_json()["status"] == 500


def test_method_not_allowed_uses_generic_error_page(client):
    response = client.post("/")
    assert response.status_code == 405
    assert "405" in response.get_data(as_text=True)


def test_seed_command(app):
    runner = app.test_cli_runner()

    result = runner.invoke(args=["seed"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        count = lambda model: db.session.scalar(select(func.count(model.id)))  # noqa: E731
        assert count(User) == 2
        assert count(Room) == 12
        assert count(Student) == 26
        assert count(Contract) == 22
        assert count(Payment) == 220
        assert db.session.scalar(select(func.count(Student.id)).where(Student.room_id.is_(None))) == 4
        for room in db.session.scalars(select(Room)):
            assert room.occupied <= room.capacity
        assert db.session.scalar(select(func.count(Room.id)).where(Room.occupied == 0)) == 1
        assert db.session.scalar(select(func.count(Room.id)).where(Room.occupied >= Room.capacity)) >= 1

    again = runner.invoke(args=["seed"])
    assert again.exit_code != 0
    assert "already has users" in again.output


def test_seeded_accounts_can_log_in(app):
    app.test_cli_runner().invoke(args=["seed"])

    admin = app.test_client()
    response = admin.post("/auth/login", data={"login": "admin", "password": "Admin123!"})
    assert response.status_code == 302
    for path in ("/", "/dashboard", "/rooms/", "/students/", "/contracts/", "/payments/", "/users/"):
        assert admin.get(path).status_code == 200

    student = app.test_client()
    student.post("/auth/login", data={"login": "miras", "password": "User123!"})
    html = student.get("/profile").get_data(as_text=True)
    assert "Мирас Сейітұлы" in html and "Келісімшарт №RK-" in html
    assert student.get("/students/").status_code == 403


def test_create_admin_command(app):
    runner = app.test_cli_runner()
    args = ["create-admin", "--username", "boss", "--email", "Boss@Example.com", "--password"]

    assert runner.invoke(args=[*args, "short"]).exit_code != 0
    assert runner.invoke(args=[*args, "LongEnough1"]).exit_code == 0
    assert "already taken" in runner.invoke(args=[*args, "LongEnough1"]).output

    with app.app_context():
        user = db.session.scalar(select(User))
        assert (user.username, user.email, user.is_admin) == ("boss", "boss@example.com", True)
