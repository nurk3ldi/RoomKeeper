from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from sqlalchemy import func, select
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
)
from wtforms.validators import (
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from app import db
from app.models import ROLE_USER, Contract, Room, Student, User
from app.utils import has_allowed_extension, looks_like_pdf

REQUIRED = "Бұл өрісті толтыру міндетті."
MAX_CONTRACT_DAYS = 5 * 366


def required():
    return InputRequired(REQUIRED)


def length(min=-1, max=-1):
    if min > 0 and max > 0:
        message = f"Ұзындығы {min}–{max} таңба аралығында болуы керек."
    elif max > 0:
        message = f"Ұзындығы {max} таңбадан аспауы керек."
    else:
        message = f"Кемінде {min} таңба болуы керек."
    return Length(min=min, max=max, message=message)


class Range(NumberRange):
    def __call__(self, form, field):
        # Unparseable input already carries its own "not a number" error.
        if field.data is not None:
            super().__call__(form, field)


def number_range(min, max):
    return Range(
        min=min, max=max, message=f"Мәні {min} мен {max} аралығында болуы керек."
    )


def strip(value):
    return value.strip() if isinstance(value, str) else value


def lower(value):
    return value.lower() if isinstance(value, str) else value


def compact_phone(value):
    if not isinstance(value, str):
        return value
    return "".join(ch for ch in value if ch not in " -()")


class Unique:
    """Reject a value another row already uses (case-insensitively)."""

    def __init__(self, column, message):
        self.column = column
        self.message = message

    def __call__(self, form, field):
        if not field.data:
            return
        model = self.column.class_
        existing = db.session.scalar(
            select(model).where(func.lower(self.column) == field.data.lower())
        )
        if existing is not None and existing.id != getattr(form.obj, "id", None):
            raise ValidationError(self.message)


class BaseForm(FlaskForm):
    class Meta:
        locales = ["kk"]

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, obj=obj, **kwargs)
        # The row being edited, so validators can tell "unchanged" from "taken".
        self.obj = obj


class LoginForm(BaseForm):
    login = StringField(
        "Логин немесе email", [required(), length(max=120)], filters=[strip]
    )
    password = PasswordField("Құпиясөз", [required()])
    remember = BooleanField("Мені есте сақта")


class RegisterForm(BaseForm):
    username = StringField(
        "Логин",
        [
            required(),
            length(3, 32),
            Regexp(
                r"^[A-Za-z0-9_.]+$",
                message="Тек латын әріптері, цифрлар, нүкте және астын сызу.",
            ),
            Unique(User.username, "Бұл логин бос емес."),
        ],
        filters=[strip],
    )
    email = StringField(
        "Email",
        [
            required(),
            length(max=120),
            Email("Email форматы қате."),
            Unique(User.email, "Бұл email тіркелген."),
        ],
        filters=[strip, lower],
    )
    password = PasswordField("Құпиясөз", [required(), length(8, 128)])
    confirm = PasswordField(
        "Құпиясөзді қайталаңыз",
        [required(), EqualTo("password", "Құпиясөздер сәйкес келмейді.")],
    )


class RoomForm(BaseForm):
    number = StringField(
        "Бөлме нөмірі",
        [
            required(),
            length(max=10),
            Regexp(r"^[\w-]+$", message="Тек әріптер, цифрлар және сызықша."),
            Unique(Room.number, "Мұндай нөмірлі бөлме бар."),
        ],
        filters=[strip],
    )
    floor = IntegerField("Қабат", [required(), number_range(1, 30)])
    capacity = IntegerField("Орын саны", [required(), number_range(1, 6)])
    monthly_price = DecimalField(
        "Айлық баға (₸)", [required(), number_range(0, 1_000_000)], places=2
    )

    def validate_capacity(self, field):
        occupied = self.obj.occupied if self.obj is not None else 0
        if field.data is not None and field.data < occupied:
            raise ValidationError(
                f"Бөлмеде {occupied} студент тұрады — орын саны одан аз бола алмайды."
            )


class StudentForm(BaseForm):
    full_name = StringField("Аты-жөні", [required(), length(3, 120)], filters=[strip])
    email = StringField(
        "Email",
        [
            required(),
            length(max=120),
            Email("Email форматы қате."),
            Unique(Student.email, "Бұл email-мен студент тіркелген."),
        ],
        filters=[strip, lower],
    )
    phone = StringField(
        "Телефон",
        [
            required(),
            Regexp(
                r"^\+?[0-9]{10,15}$",
                message="Телефон 10–15 цифрдан тұруы керек, мысалы +77011234567.",
            ),
        ],
        filters=[strip, compact_phone],
    )
    course = IntegerField("Курс", [required(), number_range(1, 6)])
    room_id = SelectField("Бөлме", coerce=int)
    user_id = SelectField("Пайдаланушы аккаунты", coerce=int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rooms = db.session.scalars(select(Room).order_by(Room.number))
        self.room_id.choices = [(0, "— Бөлмесіз —")] + [
            (room.id, f"№{room.number} ({room.occupied}/{room.capacity})")
            for room in rooms
        ]

        linked_elsewhere = select(Student.user_id).where(
            Student.user_id.is_not(None),
            Student.id != getattr(self.obj, "id", None),
        )
        users = db.session.scalars(
            select(User)
            .where(User.role == ROLE_USER, User.id.not_in(linked_elsewhere))
            .order_by(User.username)
        )
        self.user_id.choices = [(0, "— Байланыспаған —")] + [
            (user.id, f"{user.username} ({user.email})") for user in users
        ]

    def validate_room_id(self, field):
        if not field.data or field.data == getattr(self.obj, "room_id", None):
            return
        room = db.session.get(Room, field.data)
        if room is not None and room.is_full:
            raise ValidationError("Бұл бөлмеде бос орын жоқ.")


class ContractForm(BaseForm):
    student_id = SelectField("Студент", coerce=int)
    number = StringField(
        "Келісімшарт нөмірі",
        [
            required(),
            length(max=30),
            Regexp(
                r"^[A-Za-z0-9/_-]+$",
                message="Тек латын әріптері, цифрлар және / _ - таңбалары.",
            ),
            Unique(Contract.number, "Мұндай нөмірлі келісімшарт бар."),
        ],
        filters=[strip],
    )
    start_date = DateField("Басталу күні", [required()])
    end_date = DateField("Аяқталу күні", [required()])
    monthly_fee = DecimalField(
        "Айлық төлем (₸)", [required(), number_range(1, 1_000_000)], places=2
    )
    pdf = FileField("Келісімшарт файлы (PDF)")
    generate_schedule = BooleanField("Ай сайынғы төлем кестесін автоматты құру")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        students = db.session.scalars(select(Student).order_by(Student.full_name))
        self.student_id.choices = [(s.id, s.full_name) for s in students]

    def validate_end_date(self, field):
        start = self.start_date.data
        if not start or not field.data:
            return
        if field.data <= start:
            raise ValidationError("Аяқталу күні басталу күнінен кейін болуы керек.")
        if (field.data - start).days > MAX_CONTRACT_DAYS:
            raise ValidationError("Келісімшарт мерзімі 5 жылдан аспауы керек.")

    def validate_pdf(self, field):
        if not field.data:
            return
        if not has_allowed_extension(field.data.filename):
            raise ValidationError("Тек .pdf кеңейтімді файл жүктеуге болады.")
        if not looks_like_pdf(field.data):
            raise ValidationError("Файл мазмұны PDF форматына сәйкес емес.")


class PaymentForm(BaseForm):
    contract_id = SelectField("Келісімшарт", coerce=int)
    amount = DecimalField(
        "Сома (₸)", [required(), number_range(1, 10_000_000)], places=2
    )
    due_date = DateField("Төлеу мерзімі", [required()])
    paid_at = DateField("Төленген күні", [Optional()])
    comment = StringField("Түсініктеме", [length(max=200)], filters=[strip])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        contracts = db.session.scalars(
            select(Contract).join(Contract.student).order_by(Student.full_name)
        )
        self.contract_id.choices = [
            (c.id, f"{c.student.full_name} — №{c.number}") for c in contracts
        ]

    def validate_paid_at(self, field):
        if field.data and field.data > date.today():
            raise ValidationError("Төленген күні болашақта бола алмайды.")
