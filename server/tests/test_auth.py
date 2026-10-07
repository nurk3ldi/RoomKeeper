import pytest
from sqlalchemy import select

from app import db
from app.models import ROLE_USER, User
from tests.conftest import PASSWORD, TestConfig


def register(client, **overrides):
    data = {
        "username": "newuser",
        "email": "new@example.com",
        "password": PASSWORD,
        "confirm": PASSWORD,
    }
    data.update(overrides)
    return client.post("/auth/register", data=data)


def test_anonymous_is_redirected_to_login(client):
    response = client.get("/rooms/?floor=2")
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login?next=/rooms/?floor%3D2"


def test_auth_pages_are_minimal(client):
    for path, fields in (
        ("/auth/login", ("login", "password")),
        ("/auth/register", ("username", "email", "password", "confirm")),
    ):
        html = client.get(path).get_data(as_text=True)

        assert html.startswith("<!doctype html>")
        assert html.count("<input") == len(fields)  # CSRF is off in tests
        for name in fields:
            assert f'<label class="sr-only" for="{name}">' in html
            assert f'name="{name}" placeholder="' in html
        assert 'class="footer"' not in html and "<nav" not in html


def test_password_fields_have_a_show_hide_button(client):
    login = client.get("/auth/login").get_data(as_text=True)
    register = client.get("/auth/register").get_data(as_text=True)

    assert login.count('class="password-toggle" hidden') == 1
    assert register.count('class="password-toggle" hidden') == 2
    for html in (login, register):
        assert 'src="/static/js/password-toggle.js"' in html
        # The fields are masked until the visitor asks otherwise.
        assert 'type="text"' not in html.split("password-wrap", 1)[1].split("</div>", 1)[0]
    assert client.get("/static/js/password-toggle.js").status_code == 200


def test_register_creates_plain_user(app, client):
    response = register(client, email="New@Example.com")
    assert response.status_code == 302

    with app.app_context():
        user = db.session.scalar(select(User).where(User.username == "newuser"))
        assert user.role == ROLE_USER
        assert user.email == "new@example.com"
        assert user.password_hash != PASSWORD
        assert user.check_password(PASSWORD)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"username": "ab"}, "3–32 таңба"),
        ({"username": "bad name!"}, "Тек латын әріптері"),
        ({"email": "not-an-email"}, "Email форматы қате"),
        ({"password": "short", "confirm": "short"}, "8–128 таңба"),
        ({"confirm": "different123"}, "Құпиясөздер сәйкес келмейді"),
        ({"username": ""}, "Бұл өрісті толтыру міндетті"),
    ],
)
def test_register_validation(app, client, overrides, message):
    response = register(client, **overrides)
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(User)) is None


def test_register_rejects_taken_username_and_email(client, make):
    make.user("taken")
    assert "Бұл логин бос емес" in register(client, username="TAKEN").get_data(as_text=True)
    assert "Бұл email тіркелген" in register(client, email="taken@example.com").get_data(as_text=True)


@pytest.mark.parametrize("identifier", ["user", "USER", "user@example.com"])
def test_login_with_username_or_email(client, make, identifier):
    make.user("user")
    response = client.post("/auth/login", data={"login": identifier, "password": PASSWORD})
    assert response.headers["Location"] == "/dashboard"
    assert client.get("/dashboard").status_code == 200


def test_login_with_wrong_password(client, make):
    make.user("user")
    response = client.post("/auth/login", data={"login": "user", "password": "wrong-password"})
    assert response.status_code == 200
    assert "Логин немесе құпиясөз қате" in response.get_data(as_text=True)
    assert client.get("/dashboard").status_code == 302


@pytest.mark.parametrize(
    "target, expected",
    [
        ("/rooms/", "/rooms/"),
        ("https://evil.example/", "/dashboard"),
        ("//evil.example/", "/dashboard"),
        ("javascript:alert(1)", "/dashboard"),
    ],
)
def test_login_only_follows_local_next(client, make, target, expected):
    make.user("user")
    response = client.post(
        "/auth/login", query_string={"next": target}, data={"login": "user", "password": PASSWORD}
    )
    assert response.headers["Location"] == expected


def test_profile_icon_in_header_and_logout_only_on_profile(user_client, make):
    make.room(number="101")
    pages = {path: user_client.get(path).get_data(as_text=True) for path in ("/", "/dashboard", "/rooms/", "/profile")}

    for path, html in pages.items():
        # The header shows an icon with the account in its tooltip, not the name.
        assert 'title="user · Пайдаланушы"' in html
        assert ('action="/auth/logout"' in html) == (path == "/profile")
    assert 'class="profile-link active"' in pages["/profile"]
    assert 'class="profile-link"' in pages["/rooms/"]
    assert "Жүйеден шығу</button>" in pages["/profile"]


def test_logout_requires_post(user_client):
    assert user_client.get("/auth/logout").status_code == 405
    assert user_client.post("/auth/logout").headers["Location"] == "/"
    assert user_client.get("/dashboard").status_code == 302


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/students/"),
        ("get", "/students/new"),
        ("get", "/contracts/"),
        ("get", "/payments/"),
        ("get", "/users/"),
        ("get", "/rooms/new"),
        ("post", "/rooms/new"),
        ("post", "/rooms/1/delete"),
        ("post", "/students/1/delete"),
        ("post", "/payments/1/pay"),
        ("post", "/users/1/role"),
    ],
)
def test_admin_pages_are_forbidden_for_plain_users(user_client, method, path):
    response = getattr(user_client, method)(path)
    assert response.status_code == 403
    assert "Қол жеткізуге рұқсат жоқ" in response.get_data(as_text=True)


def test_plain_user_can_browse_rooms_but_sees_no_admin_controls(user_client, make):
    room_id = make.room(number="101")
    make.student(name="Secret Student", room_id=room_id)

    listing = user_client.get("/rooms/").get_data(as_text=True)
    detail = user_client.get(f"/rooms/{room_id}").get_data(as_text=True)

    assert "№101" in listing
    assert "Бөлме қосу" not in listing and "Өшіру" not in listing
    assert "Secret Student" not in detail
    assert "Студенттер" not in listing


@pytest.mark.parametrize("path", ["/", "/dashboard", "/rooms/", "/students/", "/contracts/", "/payments/", "/users/", "/profile"])
def test_admin_can_open_every_section(admin_client, path):
    assert admin_client.get(path).status_code == 200


def test_post_without_csrf_token_is_rejected(tmp_path):
    from app import create_app

    class CsrfConfig(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(CsrfConfig)
    with app.app_context():
        db.create_all()
    client = app.test_client()

    response = register(client)
    assert response.status_code == 400
    with app.app_context():
        assert db.session.scalar(select(User)) is None

    # The JSON API is exempt and answers on its own terms.
    assert client.post("/api/auth/login", json={"login": "x", "password": "y"}).status_code == 401


def test_admin_can_change_roles_but_not_their_own(app, admin_client, make):
    user_id = make.user("user")
    with app.app_context():
        admin_id = db.session.scalar(select(User.id).where(User.username == "admin"))

    admin_client.post(f"/users/{user_id}/role")
    admin_client.post(f"/users/{admin_id}/role")
    admin_client.post(f"/users/{admin_id}/delete")

    with app.app_context():
        assert db.session.get(User, user_id).is_admin
        assert db.session.get(User, admin_id).is_admin


def test_deleting_user_keeps_linked_student(app, admin_client, make):
    user_id = make.user("user")
    student_id = make.student(user_id=user_id)

    admin_client.post(f"/users/{user_id}/delete")

    with app.app_context():
        from app.models import Student

        assert db.session.get(User, user_id) is None
        assert db.session.get(Student, student_id).user_id is None
