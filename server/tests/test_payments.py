import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import db
from app.models import Payment


def form_data(contract_id, **overrides):
    data = {
        "contract_id": contract_id,
        "amount": "30000",
        "due_date": (date.today() + timedelta(days=5)).isoformat(),
        "paid_at": "",
        "comment": "",
    }
    data.update(overrides)
    return data


def statuses(response):
    return re.findall(r'badge badge-(paid|pending|overdue)"', response.get_data(as_text=True))


def test_create_edit_delete_payment(app, admin_client, make):
    contract_id = make.contract(make.student())

    response = admin_client.post("/payments/new", data=form_data(contract_id, comment="  Қазан айы  "))
    assert response.status_code == 302

    with app.app_context():
        payment = db.session.scalar(select(Payment))
        payment_id = payment.id
        assert payment.amount == Decimal("30000")
        assert payment.comment == "Қазан айы"
        assert payment.status == "pending"

    today = date.today().isoformat()
    admin_client.post(f"/payments/{payment_id}/edit", data=form_data(contract_id, amount="15000", paid_at=today))
    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        assert (payment.amount, payment.status, payment.comment) == (Decimal("15000"), "paid", None)

    admin_client.post(f"/payments/{payment_id}/delete")
    with app.app_context():
        assert db.session.get(Payment, payment_id) is None


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"amount": "0"}, "1 мен 10000000 аралығында"),
        ({"amount": ""}, "Бұл өрісті толтыру міндетті"),
        ({"due_date": ""}, "Бұл өрісті толтыру міндетті"),
        ({"paid_at": (date.today() + timedelta(days=1)).isoformat()}, "болашақта бола алмайды"),
        ({"comment": "x" * 201}, "200 таңбадан аспауы керек"),
        ({"contract_id": "999"}, "Жарамды таңдау емес"),
    ],
)
def test_payment_validation(app, admin_client, make, overrides, message):
    contract_id = make.contract(make.student())
    response = admin_client.post("/payments/new", data={**form_data(contract_id), **overrides})
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(Payment)) is None


def test_mark_paid_sets_today_once(app, admin_client, make):
    contract_id = make.contract(make.student())
    overdue = make.payment(contract_id, due_in_days=-20)
    already = make.payment(contract_id, due_in_days=-40, paid=True)

    admin_client.post(f"/payments/{overdue}/pay")
    response = admin_client.post(f"/payments/{already}/pay", follow_redirects=True)

    assert "бұрын төленген" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Payment, overdue).paid_at == date.today()
        assert db.session.get(Payment, already).paid_at == date.today() - timedelta(days=40)


def test_payment_status_filter_search_and_sort(admin_client, make):
    alice = make.contract(make.student(name="Alice Brown"), number="A-1")
    bob = make.contract(make.student(name="Bob Stone"), number="B-1")
    make.payment(alice, due_in_days=-30, paid=True, amount="100")
    make.payment(alice, due_in_days=-3, amount="300")
    make.payment(bob, due_in_days=14, amount="200")

    def listed(**params):
        return statuses(admin_client.get("/payments/", query_string=params))

    assert listed() == ["paid", "overdue", "pending"]
    assert listed(status="overdue") == ["overdue"]
    assert listed(status="paid") == ["paid"]
    assert listed(status="pending") == ["pending"]
    assert listed(status="bogus") == ["paid", "overdue", "pending"]
    assert listed(q="bob") == ["pending"]
    assert listed(q="A-1") == ["paid", "overdue"]
    assert listed(sort="amount", order="desc") == ["overdue", "pending", "paid"]


def test_actions_return_to_the_page_they_came_from(admin_client, make):
    contract_id = make.contract(make.student())
    payment_id = make.payment(contract_id, due_in_days=-1)
    back = f"/contracts/{contract_id}"

    response = admin_client.post(f"/payments/{payment_id}/pay", query_string={"next": back})
    assert response.headers["Location"] == back

    response = admin_client.post(f"/payments/{payment_id}/delete", query_string={"next": "https://evil.example"})
    assert response.headers["Location"] == "/payments/"

    html = admin_client.get("/payments/new", query_string={"next": "javascript:alert(1)"}).get_data(as_text=True)
    assert "javascript:" not in html


def test_contract_page_shows_payments_and_debt(admin_client, make):
    contract_id = make.contract(make.student(name="Alice Brown"), number="A-1")
    make.payment(contract_id, due_in_days=-3, amount="45000")

    html = admin_client.get(f"/contracts/{contract_id}").get_data(as_text=True)
    assert statuses(admin_client.get(f"/contracts/{contract_id}")) == ["overdue"]
    assert "<strong>45 000 ₸</strong>" in html
