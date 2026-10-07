from datetime import date

from app.models import (
    ROLE_ADMIN,
    ROLE_USER,
    STATUS_OVERDUE,
    STATUS_PAID,
    STATUS_PENDING,
)

PAYMENT_STATUS_LABELS = {
    STATUS_PAID: "Төленді",
    STATUS_PENDING: "Күтілуде",
    STATUS_OVERDUE: "Мерзімі өтті",
}
CONTRACT_STATE_LABELS = {
    "active": "Қолданыста",
    "upcoming": "Басталмаған",
    "expired": "Аяқталған",
}
ROLE_LABELS = {ROLE_ADMIN: "Әкімші", ROLE_USER: "Пайдаланушы"}


def money(value):
    if value is None:
        return "—"
    return f"{value:,.0f}".replace(",", " ") + " ₸"


def format_date(value):
    return value.strftime("%d.%m.%Y") if value else "—"


def register(app):
    app.add_template_filter(money, "money")
    app.add_template_filter(format_date, "date")

    @app.context_processor
    def inject_labels():
        return {
            "payment_status_labels": PAYMENT_STATUS_LABELS,
            "contract_state_labels": CONTRACT_STATE_LABELS,
            "role_labels": ROLE_LABELS,
            "today": date.today(),
        }
