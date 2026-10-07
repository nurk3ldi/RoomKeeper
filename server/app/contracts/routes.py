from io import BytesIO

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from sqlalchemy.orm import contains_eager
from werkzeug.utils import secure_filename

from app import db
from app.contract_pdf import render_contract_pdf
from app.contracts import bp
from app.forms import ContractForm
from app.models import Contract, Student
from app.utils import (
    admin_required,
    apply_sort,
    delete_contract_pdf,
    paginate,
    save_contract_pdf,
)

SORT_COLUMNS = {
    "number": Contract.number,
    "student": Student.full_name,
    "start": Contract.start_date,
    "end": Contract.end_date,
    "fee": Contract.monthly_fee,
}
STATES = ("active", "upcoming", "expired")


def save_contract(contract, form):
    """Copy form data onto `contract`; return the PDF name it replaced."""
    contract.student_id = form.student_id.data
    contract.number = form.number.data
    contract.start_date = form.start_date.data
    contract.end_date = form.end_date.data
    contract.monthly_fee = form.monthly_fee.data

    replaced = None
    if form.pdf.data:
        replaced = contract.pdf_filename
        contract.pdf_filename, contract.pdf_original_name = save_contract_pdf(
            form.pdf.data
        )
    return replaced


@bp.get("/")
@admin_required
def index():
    query = (
        select(Contract)
        .join(Contract.student)
        .options(contains_eager(Contract.student))
    )

    q = request.args.get("q", "").strip()
    if q:
        query = query.where(
            or_(
                Contract.number.icontains(q, autoescape=True),
                Student.full_name.icontains(q, autoescape=True),
            )
        )

    state = request.args.get("state", "")
    if state in STATES:
        query = query.where(Contract.state_filter(state))

    query, sort, order = apply_sort(query, SORT_COLUMNS, "start")
    return render_template(
        "contracts/list.html",
        page=paginate(query.order_by(Contract.id)),
        q=q,
        state=state,
        sort=sort,
        order=order,
    )


@bp.get("/<int:contract_id>")
@admin_required
def detail(contract_id):
    contract = db.get_or_404(Contract, contract_id)
    return render_template("contracts/detail.html", contract=contract)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    form = ContractForm(student_id=request.args.get("student_id", type=int))
    if not form.student_id.choices:
        flash("Келісімшарт жасау үшін алдымен студент қосыңыз.", "warning")
        return redirect(url_for("students.create"))

    if form.validate_on_submit():
        contract = Contract()
        save_contract(contract, form)
        if form.generate_schedule.data:
            contract.payments = contract.build_schedule()
        db.session.add(contract)
        db.session.commit()
        flash(f"№{contract.number} келісімшарт қосылды.", "success")
        return redirect(url_for("contracts.detail", contract_id=contract.id))
    return render_template("contracts/form.html", form=form, contract=None)


@bp.route("/<int:contract_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(contract_id):
    contract = db.get_or_404(Contract, contract_id)
    form = ContractForm(obj=contract)
    if form.validate_on_submit():
        replaced = save_contract(contract, form)
        db.session.commit()
        delete_contract_pdf(replaced)
        flash(f"№{contract.number} келісімшарт жаңартылды.", "success")
        return redirect(url_for("contracts.detail", contract_id=contract.id))
    return render_template("contracts/form.html", form=form, contract=contract)


@bp.post("/<int:contract_id>/delete")
@admin_required
def delete(contract_id):
    contract = db.get_or_404(Contract, contract_id)
    number, pdf_file = contract.number, contract.pdf_filename
    db.session.delete(contract)
    db.session.commit()
    delete_contract_pdf(pdf_file)
    flash(f"№{number} келісімшарт өшірілді.", "success")
    return redirect(url_for("contracts.index"))


@bp.get("/<int:contract_id>/pdf")
@login_required
def download(contract_id):
    contract = db.get_or_404(Contract, contract_id)
    is_owner = contract.student.user_id == current_user.id
    if not (current_user.is_admin or is_owner):
        abort(403)

    # ?download=1 saves the file instead of opening it in the browser.
    as_attachment = request.args.get("download") == "1"
    if contract.pdf_filename:
        return send_from_directory(
            current_app.config["UPLOAD_FOLDER"],
            contract.pdf_filename,
            mimetype="application/pdf",
            as_attachment=as_attachment,
            download_name=contract.pdf_original_name,
        )
    # No uploaded file: the system writes the agreement itself.
    return send_file(
        BytesIO(render_contract_pdf(contract)),
        mimetype="application/pdf",
        as_attachment=as_attachment,
        download_name=secure_filename(f"kelisimshart-{contract.number}.pdf"),
    )


@bp.post("/<int:contract_id>/pdf/delete")
@admin_required
def delete_pdf(contract_id):
    contract = db.get_or_404(Contract, contract_id)
    pdf_file = contract.pdf_filename
    contract.pdf_filename = contract.pdf_original_name = None
    db.session.commit()
    delete_contract_pdf(pdf_file)
    flash("Келісімшарт файлы өшірілді.", "success")
    return redirect(url_for("contracts.detail", contract_id=contract.id))
