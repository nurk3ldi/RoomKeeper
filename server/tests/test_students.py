import re

import pytest
from sqlalchemy import func, select

from app import db
from app.models import Contract, Payment, Student, User
from tests.conftest import login


def form_data(**overrides):
    data = {
        "full_name": "Мирас Сейітұлы",
        "email": "miras@example.com",
        "phone": "+7 (701) 123-45-67",
        "course": "2",
        "room_id": "0",
    }
    data.update(overrides)
    return data


def names(response):
    return re.findall(r'<a href="/students/\d+">([^<]+)</a>', response.get_data(as_text=True))


def test_create_edit_delete_student(app, admin_client, make):
    room_id = make.room(capacity=2)

    response = admin_client.post("/students/new", data=form_data(room_id=room_id))
    assert response.status_code == 302

    with app.app_context():
        student = db.session.scalar(select(Student))
        student_id = student.id
        assert student.phone == "+77011234567"
        assert student.room_id == room_id

    admin_client.post(f"/students/{student_id}/edit", data=form_data(course="3", room_id="0"))
    with app.app_context():
        student = db.session.get(Student, student_id)
        assert (student.course, student.room_id) == (3, None)

    admin_client.post(f"/students/{student_id}/delete")
    with app.app_context():
        assert db.session.get(Student, student_id) is None


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"full_name": "Аб"}, "3–120 таңба"),
        ({"email": "wrong@"}, "Email форматы қате"),
        ({"phone": "12345"}, "Телефон 10–15 цифрдан тұруы керек"),
        ({"phone": "+7701abc4567"}, "Телефон 10–15 цифрдан тұруы керек"),
        ({"course": "9"}, "1 мен 6 аралығында"),
        ({"room_id": "12345"}, "Жарамды таңдау емес"),
    ],
)
def test_student_validation(app, admin_client, overrides, message):
    response = admin_client.post("/students/new", data=form_data(**overrides))
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(Student)) is None


def test_phone_and_course_are_optional(app, admin_client):
    response = admin_client.post("/students/new", data=form_data(phone="", course=""))
    assert response.status_code == 302

    with app.app_context():
        student = db.session.scalar(select(Student))
        assert (student.phone, student.course) == (None, None)
        student_id = student.id

    # Pages that list the student cope with the missing values.
    for path in ("/students/", f"/students/{student_id}", f"/students/{student_id}/edit"):
        assert admin_client.get(path).status_code == 200


def test_student_cannot_be_put_into_full_room(app, admin_client, make):
    room_id = make.room(capacity=1)
    resident = make.student(room_id=room_id)

    response = admin_client.post("/students/new", data=form_data(room_id=room_id))
    assert "Бұл бөлмеде бос орын жоқ" in response.get_data(as_text=True)

    # Editing someone who already lives there must still work.
    response = admin_client.post(
        f"/students/{resident}/edit", data=form_data(email="resident@example.com", room_id=room_id)
    )
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Student, resident).room_id == room_id


def test_student_email_must_be_unique(admin_client, make):
    make.student()
    response = admin_client.post("/students/new", data=form_data(email="STUDENT1@example.com"))
    assert "Бұл email-мен студент тіркелген" in response.get_data(as_text=True)


def test_student_search_filter_sort(admin_client, make):
    room_id = make.room(number="101")
    make.student(name="Alice Brown", room_id=room_id, course=2)
    make.student(name="Bob Stone", course=1)
    make.student(name="Carol Brown", course=1)

    def listed(**params):
        return names(admin_client.get("/students/", query_string=params))

    assert listed() == ["Alice Brown", "Bob Stone", "Carol Brown"]
    assert listed(q="brown") == ["Alice Brown", "Carol Brown"]
    assert listed(q="student2@") == ["Bob Stone"]
    assert listed(q="_") == []
    assert listed(room="none") == ["Bob Stone", "Carol Brown"]
    assert listed(room=room_id) == ["Alice Brown"]
    assert listed(course=1, q="brown") == ["Carol Brown"]
    assert listed(sort="name", order="desc") == ["Carol Brown", "Bob Stone", "Alice Brown"]
    assert listed(sort="course") == ["Bob Stone", "Carol Brown", "Alice Brown"]


def test_student_list_is_paginated(admin_client, make):
    for index in range(12):
        make.student(name=f"Student {index:02d}")

    assert len(names(admin_client.get("/students/"))) == 5
    assert names(admin_client.get("/students/?page=3")) == ["Student 10", "Student 11"]


def test_search_text_is_escaped_in_html(admin_client):
    html = admin_client.get("/students/?q=<script>alert(1)</script>").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_deleting_student_removes_contracts_and_payments(app, admin_client, make):
    student_id = make.student()
    contract_id = make.contract(student_id)
    make.payment(contract_id)
    other_contract = make.contract(make.student())
    make.payment(other_contract)

    admin_client.post(f"/students/{student_id}/delete")

    with app.app_context():
        assert db.session.scalars(select(Contract.id)).all() == [other_contract]
        assert db.session.scalar(select(func.count(Payment.id))) == 1


def test_deleting_student_removes_their_account_too(app, admin_client, make):
    account = make.user("resident")
    bystander = make.user("bystander")
    student_id = make.student(user_id=account)
    make.student(user_id=bystander)

    admin_client.post(f"/students/{student_id}/delete")

    with app.app_context():
        assert db.session.get(User, account) is None
        assert db.session.get(User, bystander) is not None
    # The deleted student can no longer log in.
    client = app.test_client()
    login(client, "resident")
    assert client.get("/dashboard").status_code == 302


def test_deleting_a_student_record_never_deletes_an_admin_account(app, admin_client, make):
    with app.app_context():
        admin_id = db.session.scalar(select(User.id).where(User.username == "admin"))
    student_id = make.student(user_id=admin_id)

    admin_client.post(f"/students/{student_id}/delete")

    with app.app_context():
        assert db.session.get(Student, student_id) is None
        assert db.session.get(User, admin_id).is_admin
    assert admin_client.get("/dashboard").status_code == 200


def test_linked_user_sees_own_data_on_profile(app, make):
    owner = make.user("owner")
    make.user("stranger")
    room_id = make.room(number="305")
    contract_id = make.contract(make.student(name="Owner Student", room_id=room_id, user_id=owner), number="MINE-1")
    make.payment(contract_id, due_in_days=-2)
    make.contract(make.student(name="Other Student"), number="OTHER-1")

    client = app.test_client()
    login(client, "owner")
    html = client.get("/profile").get_data(as_text=True)
    assert "Owner Student" in html and "№305" in html and "MINE-1" in html
    assert "Мерзімі өтті" in html
    assert "OTHER-1" not in html and "Төленді</button>" not in html

    stranger = app.test_client()
    login(stranger, "stranger")
    html = stranger.get("/profile").get_data(as_text=True)
    assert "MINE-1" not in html and "Owner Student" not in html


def test_admin_profile_describes_admin_rights(admin_client):
    html = admin_client.get("/profile").get_data(as_text=True)

    assert "Әкімші құқықтары" in html
    assert "Сіз жатақхана жүйесінің әкімшісісіз" in html
    # The advice meant for unlinked students makes no sense for an admin.
    assert "әкімшіге хабарласыңыз" not in html


def test_editing_a_student_keeps_the_account_link(app, admin_client, make):
    user_id = make.user("user")
    student_id = make.student(user_id=user_id)

    form = admin_client.get(f"/students/{student_id}/edit").get_data(as_text=True)
    response = admin_client.post(f"/students/{student_id}/edit", data=form_data(course="4"))

    assert "Пайдаланушы аккаунты" not in form and 'name="user_id"' not in form
    assert response.status_code == 302
    with app.app_context():
        student = db.session.get(Student, student_id)
        assert (student.course, student.user_id) == (4, user_id)
    # The account is still shown on the student's page, read-only.
    assert "Аккаунт" in admin_client.get(f"/students/{student_id}").get_data(as_text=True)
