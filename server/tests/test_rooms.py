import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import db
from app.models import Room

VALID = {"number": "101", "floor": "1", "capacity": "3", "monthly_price": "25000"}


def room_numbers(response):
    """Room numbers in the order the list page shows them."""
    return re.findall(r">№([\w-]+)</a>", response.get_data(as_text=True))


def test_create_edit_delete_room(app, admin_client):
    response = admin_client.post("/rooms/new", data=VALID)
    assert response.status_code == 302

    with app.app_context():
        room = db.session.scalar(select(Room))
        room_id = room.id
        assert (room.number, room.floor, room.capacity) == ("101", 1, 3)
        assert room.monthly_price == Decimal("25000")

    admin_client.post(f"/rooms/{room_id}/edit", data={**VALID, "number": "102", "capacity": "4"})
    with app.app_context():
        room = db.session.get(Room, room_id)
        assert (room.number, room.capacity) == ("102", 4)

    assert "№102" in admin_client.get(f"/rooms/{room_id}").get_data(as_text=True)

    admin_client.post(f"/rooms/{room_id}/delete")
    with app.app_context():
        assert db.session.get(Room, room_id) is None


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"number": ""}, "Бұл өрісті толтыру міндетті"),
        ({"number": "12345678901"}, "10 таңбадан аспауы керек"),
        ({"number": "<b>1</b>"}, "Тек әріптер, цифрлар және сызықша"),
        ({"floor": "0"}, "1 мен 30 аралығында"),
        ({"capacity": "7"}, "1 мен 6 аралығында"),
        ({"capacity": "abc"}, "Жарамды бүтін сан мәні емес"),
        ({"monthly_price": "-5"}, "0 мен 1000000 аралығында"),
    ],
)
def test_room_validation(app, admin_client, overrides, message):
    response = admin_client.post("/rooms/new", data={**VALID, **overrides})
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(Room)) is None


def test_room_number_must_be_unique(admin_client, make):
    make.room(number="A1")
    other = make.room(number="B2")

    response = admin_client.post("/rooms/new", data={**VALID, "number": "a1"})
    assert "Мұндай нөмірлі бөлме бар" in response.get_data(as_text=True)

    response = admin_client.post(f"/rooms/{other}/edit", data={**VALID, "number": "A1"})
    assert "Мұндай нөмірлі бөлме бар" in response.get_data(as_text=True)

    # Saving a room under its own number is not a conflict.
    assert admin_client.post(f"/rooms/{other}/edit", data={**VALID, "number": "B2"}).status_code == 302


def test_occupied_room_cannot_be_deleted_or_shrunk(app, admin_client, make):
    room_id = make.room(number="201", capacity=3)
    make.student(room_id=room_id)
    make.student(room_id=room_id)

    response = admin_client.post(f"/rooms/{room_id}/delete", follow_redirects=True)
    assert "алдымен оларды көшіріңіз" in response.get_data(as_text=True)

    response = admin_client.post(f"/rooms/{room_id}/edit", data={**VALID, "number": "201", "capacity": "1"})
    assert "орын саны одан аз бола алмайды" in response.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(Room, room_id).capacity == 3


def test_room_search_filter_and_sort(admin_client, make):
    full = make.room(number="101", floor=1, capacity=1, price="40000")
    make.room(number="102", floor=1, capacity=2, price="30000")
    partly = make.room(number="201", floor=2, capacity=2, price="20000")
    make.student(room_id=full)
    make.student(room_id=partly)

    def listed(**params):
        return room_numbers(admin_client.get("/rooms/", query_string=params))

    assert listed() == ["101", "102", "201"]
    assert listed(q="20") == ["201"]
    assert listed(q="%") == []
    assert listed(floor=1) == ["101", "102"]
    assert listed(availability="free") == ["102", "201"]
    assert listed(availability="full") == ["101"]
    assert listed(availability="empty") == ["102"]
    assert listed(floor=1, availability="free") == ["102"]
    assert listed(sort="price") == ["201", "102", "101"]
    assert listed(sort="price", order="desc") == ["101", "102", "201"]
    assert listed(sort="occupied", order="desc")[-1] == "102"
    # Unknown sort keys fall back to the default instead of reaching SQL.
    assert listed(sort="monthly_price; DROP TABLE rooms") == ["101", "102", "201"]


def test_room_list_is_paginated(admin_client, make):
    for index in range(1, 8):
        make.room(number=f"10{index}")

    first = admin_client.get("/rooms/")
    second = admin_client.get("/rooms/?page=2")

    assert room_numbers(first) == ["101", "102", "103", "104", "105"]
    assert room_numbers(second) == ["106", "107"]
    assert "Барлығы: 7" in first.get_data(as_text=True)
    assert 'href="/rooms/?page=2"' in first.get_data(as_text=True)
    assert room_numbers(admin_client.get("/rooms/?page=99")) == []
    # per_page cannot be raised from the URL.
    assert len(room_numbers(admin_client.get("/rooms/?per_page=100"))) == 5


def test_pagination_links_keep_filters(admin_client, make):
    for index in range(1, 8):
        make.room(number=f"30{index}", floor=3)

    html = admin_client.get("/rooms/?floor=3&sort=price").get_data(as_text=True)
    assert 'href="/rooms/?floor=3&amp;sort=price&amp;page=2"' in html


def test_missing_room_is_404(admin_client):
    assert admin_client.get("/rooms/999").status_code == 404
    assert admin_client.post("/rooms/999/delete").status_code == 404
