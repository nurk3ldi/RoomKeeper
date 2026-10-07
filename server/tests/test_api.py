import pytest
from sqlalchemy import select

from app import db
from app.models import Room
from tests.conftest import PASSWORD

ROOM = {"number": "101", "floor": 1, "capacity": 3, "monthly_price": 25000}


def test_health_is_public(client):
    assert client.get("/api/health").get_json() == {"status": "ok", "db": "ok"}


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/api/rooms"),
        ("get", "/api/rooms/1"),
        ("post", "/api/rooms"),
        ("put", "/api/rooms/1"),
        ("delete", "/api/rooms/1"),
        ("get", "/api/students"),
        ("get", "/api/payments"),
        ("get", "/api/stats"),
        ("get", "/api/auth/me"),
    ],
)
def test_api_requires_login_and_answers_in_json(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_api_login_logout(client, make):
    make.user("user")

    assert client.post("/api/auth/login", json={"login": "user", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", data="not json").status_code == 400
    assert client.post("/api/auth/login", json=["user", PASSWORD]).status_code == 400

    response = client.post("/api/auth/login", json={"login": "user", "password": PASSWORD})
    assert response.get_json()["user"] == {
        "id": 1,
        "username": "user",
        "email": "user@example.com",
        "role": "user",
    }
    assert client.get("/api/auth/me").get_json()["user"]["username"] == "user"

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_room_crud_cycle(app, admin_client):
    created = admin_client.post("/api/rooms", json=ROOM)
    assert created.status_code == 201
    room = created.get_json()
    assert room == {
        "id": room["id"],
        "number": "101",
        "floor": 1,
        "capacity": 3,
        "monthly_price": 25000.0,
        "occupied": 0,
        "free_places": 3,
        "occupancy_percent": 0,
    }
    url = f"/api/rooms/{room['id']}"

    assert admin_client.get(url).get_json() == room

    # PUT accepts a partial body and keeps the other fields.
    updated = admin_client.put(url, json={"capacity": 4})
    assert updated.status_code == 200
    assert updated.get_json()["capacity"] == 4
    assert updated.get_json()["number"] == "101"

    listing = admin_client.get("/api/rooms").get_json()
    assert listing["total"] == 1 and listing["items"][0]["capacity"] == 4

    assert admin_client.delete(url).status_code == 204
    assert admin_client.get(url).status_code == 404
    with app.app_context():
        assert db.session.scalar(select(Room)) is None


@pytest.mark.parametrize(
    "payload, field",
    [
        ({**ROOM, "capacity": 0}, "capacity"),
        ({**ROOM, "capacity": "many"}, "capacity"),
        ({**ROOM, "floor": 99}, "floor"),
        ({**ROOM, "monthly_price": -1}, "monthly_price"),
        ({**ROOM, "number": ""}, "number"),
        ({"number": "101"}, "floor"),
        ({}, "number"),
    ],
)
def test_room_api_validation(app, admin_client, payload, field):
    response = admin_client.post("/api/rooms", json=payload)
    body = response.get_json()
    assert response.status_code == 400
    assert body["error"] == "Validation failed"
    assert field in body["fields"]
    with app.app_context():
        assert db.session.scalar(select(Room)) is None


def test_room_api_rejects_duplicates_and_bad_updates(admin_client, make):
    make.room(number="101")
    room_id = make.room(number="102", capacity=2)
    make.student(room_id=room_id)

    assert "number" in admin_client.post("/api/rooms", json=ROOM).get_json()["fields"]
    assert "number" in admin_client.put(f"/api/rooms/{room_id}", json={"number": "101"}).get_json()["fields"]
    assert "capacity" in admin_client.put(f"/api/rooms/{room_id}", json={"capacity": 0}).get_json()["fields"]

    conflict = admin_client.delete(f"/api/rooms/{room_id}")
    assert conflict.status_code == 409
    assert conflict.get_json()["message"] == "Room still has students assigned."


def test_room_api_ignores_unknown_fields(app, admin_client):
    response = admin_client.post("/api/rooms", json={**ROOM, "id": 500, "occupied": 3})
    assert response.status_code == 201
    assert response.get_json()["id"] != 500
    assert response.get_json()["occupied"] == 0


def test_plain_user_can_read_rooms_but_not_write(user_client, make):
    room_id = make.room(number="101")

    assert user_client.get("/api/rooms").get_json()["total"] == 1
    assert user_client.get(f"/api/rooms/{room_id}").status_code == 200
    assert user_client.get("/api/stats").status_code == 200

    for response in (
        user_client.post("/api/rooms", json=ROOM),
        user_client.put(f"/api/rooms/{room_id}", json={"capacity": 5}),
        user_client.delete(f"/api/rooms/{room_id}"),
        user_client.get("/api/students"),
        user_client.get("/api/payments"),
    ):
        assert response.status_code == 403
        assert response.get_json()["error"] == "Forbidden"


def test_room_list_filters_and_pagination(admin_client, make):
    full = make.room(number="101", floor=1, capacity=1)
    make.student(room_id=full)
    for index in range(2, 9):
        make.room(number=f"20{index}", floor=2)

    everything = admin_client.get("/api/rooms").get_json()
    assert (everything["total"], everything["pages"], everything["per_page"]) == (8, 2, 5)
    assert len(everything["items"]) == 5

    assert len(admin_client.get("/api/rooms?page=2").get_json()["items"]) == 3
    assert admin_client.get("/api/rooms?floor=1").get_json()["total"] == 1
    assert admin_client.get("/api/rooms?available=1").get_json()["total"] == 7
    assert admin_client.get("/api/rooms?per_page=500").get_json()["per_page"] == 5


def test_students_and_payments_endpoints(admin_client, make):
    room_id = make.room(number="101")
    alice = make.student(name="Alice Brown", room_id=room_id)
    make.student(name="Bob Stone")
    contract_id = make.contract(alice, number="A-1")
    make.payment(contract_id, due_in_days=-3)
    make.payment(contract_id, due_in_days=9)

    students = admin_client.get("/api/students?q=alice").get_json()
    assert [s["full_name"] for s in students["items"]] == ["Alice Brown"]
    assert students["items"][0]["room_number"] == "101"
    assert admin_client.get(f"/api/students?room_id={room_id}").get_json()["total"] == 1

    overdue = admin_client.get("/api/payments?status=overdue").get_json()
    assert overdue["total"] == 1
    assert overdue["items"][0]["status"] == "overdue"
    assert overdue["items"][0]["student"] == "Alice Brown"
    assert overdue["items"][0]["contract_number"] == "A-1"
    assert admin_client.get("/api/payments").get_json()["total"] == 2

    bad = admin_client.get("/api/payments?status=late")
    assert bad.status_code == 400
    assert "status must be one of" in bad.get_json()["message"]


def test_stats_endpoint(admin_client, make):
    room_id = make.room(capacity=4)
    make.student(room_id=room_id)

    stats = admin_client.get("/api/stats").get_json()
    assert stats["occupancy_percent"] == 25
    assert stats["free_places"] == 3
    assert set(stats["payments"]) == {"paid", "pending", "overdue"}


def test_api_errors_are_json(admin_client):
    missing = admin_client.get("/api/rooms/999")
    assert missing.status_code == 404
    assert missing.get_json()["status"] == 404

    assert admin_client.get("/api/nope").get_json()["error"] == "Not Found"
    assert admin_client.patch("/api/rooms/1").get_json()["status"] == 405
    assert admin_client.post("/api/rooms", data="{broken", content_type="application/json").status_code == 400
