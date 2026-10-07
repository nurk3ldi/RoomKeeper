from datetime import date

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select
from sqlalchemy.orm import contains_eager

from app import db
from app.forms import PaymentForm
from app.models import PAYMENT_STATUSES, Contract, Payment, Student
from app.payments import bp
from app.utils import admin_required, apply_sort, paginate, safe_next_url

SORT_COLUMNS = {
    "due": Payment.due_date,
    "amount": Payment.amount,
    "paid": Payment.paid_at,
    "student": Student.full_name,
}


def save_payment(payment, form):
    payment.contract_id = form.contract_id.data
    payment.amount = form.amount.data
    payment.due_date = form.due_date.data
    payment.paid_at = form.paid_at.data
    payment.comment = form.comment.data or None


def return_url():
    """Where the user came from (?next=), falling back to the list."""
    return safe_next_url(url_for("payments.index"))


def back_to_list():
    return redirect(return_url())


def render_form(form, payment):
    return render_template(
        "payments/form.html", form=form, payment=payment, cancel_url=return_url()
    )


@bp.get("/")
@admin_required
def index():
    query = (
        select(Payment)
        .join(Payment.contract)
        .join(Contract.student)
        .options(contains_eager(Payment.contract).contains_eager(Contract.student))
    )

    q = request.args.get("q", "").strip()
    if q:
        query = query.where(
            or_(
                Student.full_name.icontains(q, autoescape=True),
                Contract.number.icontains(q, autoescape=True),
            )
        )

    status = request.args.get("status", "")
    if status in PAYMENT_STATUSES:
        query = query.where(Payment.status_filter(status))

    query, sort, order = apply_sort(query, SORT_COLUMNS, "due")
    return render_template(
        "payments/list.html",
        page=paginate(query.order_by(Payment.id)),
        q=q,
        status=status,
        sort=sort,
        order=order,
    )


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    form = PaymentForm(contract_id=request.args.get("contract_id", type=int))
    if not form.contract_id.choices:
        flash("Төлем қосу үшін алдымен келісімшарт жасаңыз.", "warning")
        return redirect(url_for("contracts.create"))

    if form.validate_on_submit():
        payment = Payment()
        save_payment(payment, form)
        db.session.add(payment)
        db.session.commit()
        flash("Төлем қосылды.", "success")
        return back_to_list()
    return render_form(form, None)


@bp.route("/<int:payment_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(payment_id):
    payment = db.get_or_404(Payment, payment_id)
    form = PaymentForm(obj=payment)
    if form.validate_on_submit():
        save_payment(payment, form)
        db.session.commit()
        flash("Төлем жаңартылды.", "success")
        return back_to_list()
    return render_form(form, payment)


@bp.post("/<int:payment_id>/pay")
@admin_required
def mark_paid(payment_id):
    payment = db.get_or_404(Payment, payment_id)
    if payment.is_paid:
        flash("Бұл төлем бұрын төленген.", "info")
    else:
        payment.paid_at = date.today()
        db.session.commit()
        flash("Төлем «төленді» деп белгіленді.", "success")
    return back_to_list()


@bp.post("/<int:payment_id>/delete")
@admin_required
def delete(payment_id):
    payment = db.get_or_404(Payment, payment_id)
    db.session.delete(payment)
    db.session.commit()
    flash("Төлем өшірілді.", "success")
    return back_to_list()
