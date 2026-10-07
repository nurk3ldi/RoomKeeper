import io
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import db
from app.models import Contract
from tests.conftest import PDF_BYTES, login


def uploads(app):
    folder = Path(app.config["UPLOAD_FOLDER"])
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def form_data(student_id, pdf=None, **overrides):
    start = date.today()
    data = {
        "student_id": student_id,
        "number": "RK-2026-001",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=200)).isoformat(),
        "monthly_fee": "30000",
    }
    data.update(overrides)
    if pdf is not None:
        content, filename = pdf
        data["pdf"] = (io.BytesIO(content), filename)
    return data


def post_contract(client, url, **kwargs):
    return client.post(url, data=form_data(**kwargs), content_type="multipart/form-data")


def only_contract(app):
    with app.app_context():
        contract = db.session.scalar(select(Contract))
        db.session.expunge(contract)
        return contract


def test_upload_stores_pdf_under_random_name(app, admin_client, make):
    student_id = make.student()

    response = post_contract(admin_client, "/contracts/new", student_id=student_id, pdf=(PDF_BYTES, "Contract 2026.pdf"))
    assert response.status_code == 302

    contract = only_contract(app)
    assert contract.pdf_original_name == "Contract_2026.pdf"
    assert contract.pdf_filename != contract.pdf_original_name
    assert len(contract.pdf_filename) == 36 and contract.pdf_filename.endswith(".pdf")
    assert uploads(app) == [contract.pdf_filename]

    download = admin_client.get(f"/contracts/{contract.id}/pdf")
    assert download.status_code == 200
    assert download.mimetype == "application/pdf"
    assert download.data == PDF_BYTES


@pytest.mark.parametrize(
    "content, filename, message",
    [
        (PDF_BYTES, "contract.exe", "Тек .pdf кеңейтімді файл"),
        (PDF_BYTES, "contract.pdf.exe", "Тек .pdf кеңейтімді файл"),
        (PDF_BYTES, "contract", "Тек .pdf кеңейтімді файл"),
        (b"MZ\x90\x00 not a pdf", "contract.pdf", "PDF форматына сәйкес емес"),
        (b"<html><script>alert(1)</script>", "page.pdf", "PDF форматына сәйкес емес"),
        (b"", "empty.pdf", "PDF форматына сәйкес емес"),
    ],
)
def test_upload_rejects_non_pdf(app, admin_client, make, content, filename, message):
    response = post_contract(admin_client, "/contracts/new", student_id=make.student(), pdf=(content, filename))

    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    assert uploads(app) == []
    with app.app_context():
        assert db.session.scalar(select(Contract)) is None


@pytest.mark.parametrize(
    "filename, stored_as",
    [
        ("../../../etc/passwd.pdf", "etc_passwd.pdf"),
        ("келісім.pdf", "contract.pdf"),
        ("C:\\Users\\me\\scan.PDF", "CUsersmescan.PDF"),
    ],
)
def test_upload_never_trusts_client_filename(app, admin_client, make, filename, stored_as):
    post_contract(admin_client, "/contracts/new", student_id=make.student(), pdf=(PDF_BYTES, filename))

    contract = only_contract(app)
    assert contract.pdf_original_name == stored_as
    assert uploads(app) == [contract.pdf_filename]
    assert "/" not in contract.pdf_filename and ".." not in contract.pdf_filename


def test_too_large_upload_is_413(app, admin_client, make):
    app.config["MAX_CONTENT_LENGTH"] = 2048
    big = PDF_BYTES + b"0" * 4096

    response = post_contract(admin_client, "/contracts/new", student_id=make.student(), pdf=(big, "big.pdf"))

    assert response.status_code == 413
    assert "Файл тым үлкен" in response.get_data(as_text=True)
    assert uploads(app) == []


def test_replacing_and_removing_pdf_cleans_up_files(app, admin_client, make):
    student_id = make.student()
    post_contract(admin_client, "/contracts/new", student_id=student_id, pdf=(PDF_BYTES, "first.pdf"))
    first = only_contract(app)

    post_contract(admin_client, f"/contracts/{first.id}/edit", student_id=student_id, pdf=(PDF_BYTES + b"v2", "second.pdf"))
    second = only_contract(app)
    assert second.pdf_filename != first.pdf_filename
    assert uploads(app) == [second.pdf_filename]

    # Saving without a new file keeps the current one.
    post_contract(admin_client, f"/contracts/{first.id}/edit", student_id=student_id, monthly_fee="31000")
    assert only_contract(app).pdf_filename == second.pdf_filename

    admin_client.post(f"/contracts/{first.id}/pdf/delete")
    assert only_contract(app).pdf_filename is None
    assert uploads(app) == []
    # With the upload gone, the system's own document is served again.
    fallback = admin_client.get(f"/contracts/{first.id}/pdf")
    assert fallback.status_code == 200
    assert fallback.data.startswith(b"%PDF-") and b"v2" not in fallback.data[-10:]


def test_every_contract_has_a_generated_document(app, admin_client, make):
    contract_id = make.contract(make.student(name="Мирас Сейітұлы"), number="RK/2026-7")
    make.payment(contract_id)

    opened = admin_client.get(f"/contracts/{contract_id}/pdf")
    saved = admin_client.get(f"/contracts/{contract_id}/pdf?download=1")

    assert opened.status_code == 200 and opened.mimetype == "application/pdf"
    assert opened.data.startswith(b"%PDF-") and len(opened.data) > 5000
    assert opened.headers["Content-Disposition"].startswith("inline")
    # Nothing is written to disk for it, and the file name is safe to save.
    assert uploads(app) == []
    assert saved.headers["Content-Disposition"] == "attachment; filename=kelisimshart-RK_2026-7.pdf"

    page = admin_client.get(f"/contracts/{contract_id}").get_data(as_text=True)
    assert "автоматты жасайды" in page and "Жүктеп алу" in page and "Өз файлын жүктеу" in page


def test_uploaded_file_replaces_the_generated_document(app, admin_client, make):
    student_id = make.student()
    post_contract(admin_client, "/contracts/new", student_id=student_id, pdf=(PDF_BYTES, "signed.pdf"))
    contract = only_contract(app)

    assert admin_client.get(f"/contracts/{contract.id}/pdf").data == PDF_BYTES
    saved = admin_client.get(f"/contracts/{contract.id}/pdf?download=1")
    assert saved.headers["Content-Disposition"] == "attachment; filename=signed.pdf"
    page = admin_client.get(f"/contracts/{contract.id}").get_data(as_text=True)
    assert "Жүктелген файл: signed.pdf" in page and "Файлды өшіру" in page


def test_generated_document_states_the_contract_terms(app, make):
    from datetime import date

    from app.contract_pdf import contract_preamble, contract_sections, contract_title, long_date, signing_date

    room_id = make.room(number="204", floor=2)
    housed = make.contract(
        make.student(name="Мирас Сейітұлы", room_id=room_id),
        number="RK-1",
        start=date(2026, 9, 5),
        end=date(2027, 6, 30),
        fee="22000",
    )
    unhoused = make.contract(make.student(name="No Room"), number="RK-2")
    make.payment(housed)

    with app.app_context():
        contract = db.session.get(Contract, housed)
        text = " ".join(clause for _, clauses in contract_sections(contract) for clause in clauses)

        assert contract_title(contract).endswith("№ RK-1")
        assert "Мирас Сейітұлы" in contract_preamble(contract)
        assert "2-қабаттағы №204 бөлмеден" in text
        assert "05.09.2026 – 30.06.2027" in text
        assert "айына 22 000 теңге" in text
        assert "әр айдың 5-күнінен" in text
        assert "қосымшасында" in text
        assert long_date(signing_date(contract)) == "2026 жылғы 5 қыркүйек"

        other = db.session.get(Contract, unhoused)
        other_text = " ".join(clause for _, clauses in contract_sections(other) for clause in clauses)
        assert "бөлме нөмірі орналастыру кезінде белгіленеді" in other_text
        assert "қосымшасында" not in other_text


def test_deleting_contract_or_student_deletes_pdf(app, admin_client, make):
    student_id = make.student()
    post_contract(admin_client, "/contracts/new", student_id=student_id, pdf=(PDF_BYTES, "a.pdf"))
    contract = only_contract(app)
    admin_client.post(f"/contracts/{contract.id}/delete")
    assert uploads(app) == []

    post_contract(admin_client, "/contracts/new", student_id=student_id, pdf=(PDF_BYTES, "b.pdf"))
    assert len(uploads(app)) == 1
    admin_client.post(f"/students/{student_id}/delete")
    assert uploads(app) == []


def test_pdf_is_only_served_to_admin_and_owner(app, admin_client, make):
    owner = make.user("owner")
    make.user("stranger")
    student_id = make.student(user_id=owner)
    post_contract(admin_client, "/contracts/new", student_id=student_id, pdf=(PDF_BYTES, "a.pdf"))
    contract = only_contract(app)
    url = f"/contracts/{contract.id}/pdf"

    assert app.test_client().get(url).status_code == 302
    assert app.test_client().get(f"/static/../uploads/{contract.pdf_filename}").status_code == 404

    owner_client = app.test_client()
    login(owner_client, "owner")
    assert owner_client.get(url).data == PDF_BYTES

    stranger_client = app.test_client()
    login(stranger_client, "stranger")
    assert stranger_client.get(url).status_code == 403

    # The same rule guards the document the system writes itself.
    admin_client.post(f"/contracts/{contract.id}/pdf/delete")
    assert owner_client.get(url).data.startswith(b"%PDF-")
    assert stranger_client.get(url).status_code == 403
    assert app.test_client().get(url).status_code == 302


def test_schedule_is_generated_on_request(app, admin_client, make):
    student_id = make.student()
    post_contract(
        admin_client,
        "/contracts/new",
        student_id=student_id,
        start_date="2026-09-01",
        end_date="2027-06-30",
        generate_schedule="y",
    )
    with app.app_context():
        contract = db.session.scalar(select(Contract))
        assert len(contract.payments) == 10
        assert all(p.amount == contract.monthly_fee for p in contract.payments)

    post_contract(admin_client, "/contracts/new", student_id=student_id, number="RK-2")
    with app.app_context():
        second = db.session.scalar(select(Contract).where(Contract.number == "RK-2"))
        assert second.payments == []


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"end_date": "2020-01-01"}, "басталу күнінен кейін болуы керек"),
        ({"start_date": "2026-01-01", "end_date": "2040-01-01"}, "5 жылдан аспауы керек"),
        ({"number": "bad number"}, "Тек латын әріптері, цифрлар"),
        ({"monthly_fee": "0"}, "1 мен 1000000 аралығында"),
        ({"start_date": "not-a-date"}, "Жарамды күн мәні емес"),
        ({"student_id": "999"}, "Жарамды таңдау емес"),
    ],
)
def test_contract_validation(app, admin_client, make, overrides, message):
    data = {"student_id": make.student(), **overrides}
    response = post_contract(admin_client, "/contracts/new", **data)
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(Contract)) is None


def test_contract_list_search_and_state_filter(admin_client, make):
    today = date.today()
    alice = make.student(name="Alice Brown")
    bob = make.student(name="Bob Stone")
    make.contract(alice, number="ACTIVE-1")
    make.contract(bob, number="OLD-1", start=today - timedelta(days=400), end=today - timedelta(days=100))

    def listed(**params):
        html = admin_client.get("/contracts/", query_string=params).get_data(as_text=True)
        return [n for n in ("ACTIVE-1", "OLD-1") if f"№{n}" in html]

    assert listed() == ["ACTIVE-1", "OLD-1"]
    assert listed(q="old") == ["OLD-1"]
    assert listed(q="alice") == ["ACTIVE-1"]
    assert listed(state="expired") == ["OLD-1"]
    assert listed(state="active") == ["ACTIVE-1"]
    assert listed(state="upcoming") == []


def test_contract_form_without_students_redirects(admin_client):
    response = admin_client.get("/contracts/new")
    assert response.status_code == 302
    assert response.headers["Location"] == "/students/new"
