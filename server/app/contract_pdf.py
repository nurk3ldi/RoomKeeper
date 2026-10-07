"""The dormitory agreement the system writes for a contract.

Every contract has this document from the moment it exists: it is rendered
from the contract's data on request, so it is never out of date and needs
no stored file. An uploaded PDF, when there is one, takes its place.
"""

from pathlib import Path

from fpdf import FPDF

from app.template_helpers import format_date

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT = "DejaVuSerif"

DORMITORY = "«RoomKeeper» студенттер жатақханасы"
MONTHS = (
    "қаңтар",
    "ақпан",
    "наурыз",
    "сәуір",
    "мамыр",
    "маусым",
    "шілде",
    "тамыз",
    "қыркүйек",
    "қазан",
    "қараша",
    "желтоқсан",
)


def long_date(value):
    return f"{value.year} жылғы {value.day} {MONTHS[value.month - 1]}"


def tenge(amount):
    return f"{amount:,.0f}".replace(",", " ") + " теңге"


def signing_date(contract):
    """An agreement is signed no later than the day the stay begins."""
    return min(contract.created_at.date(), contract.start_date)


def contract_title(contract):
    return f"ЖАТАҚХАНАДА ТҰРУ ТУРАЛЫ КЕЛІСІМШАРТ\n№ {contract.number}"


def contract_preamble(contract):
    return (
        f"{DORMITORY} (бұдан әрі — «Жатақхана») жатақхана әкімшілігі атынан бір "
        f"тараптан және {contract.student.full_name} (бұдан әрі — «Тұрғын») екінші "
        "тараптан, бірлесіп «Тараптар» деп аталып, төмендегілер туралы осы "
        "келісімшартты жасасты."
    )


def contract_sections(contract):
    """The agreement as (heading, [numbered clauses]) pairs."""
    student = contract.student
    room = student.room
    if room is not None:
        place = (
            f"Жатақхана Тұрғынға {room.floor}-қабаттағы №{room.number} бөлмеден бір "
            "төсек-орынды уақытша тұру үшін береді"
        )
    else:
        place = (
            "Жатақхана Тұрғынға жатақханадан бір төсек-орынды уақытша тұру үшін "
            "береді (бөлме нөмірі орналастыру кезінде белгіленеді)"
        )

    payment = [
        f"Тұру ақысы айына {tenge(contract.monthly_fee)} құрайды.",
        f"Төлем ай сайын, әр айдың {contract.start_date.day}-күнінен кешіктірілмей "
        "төленеді.",
    ]
    if contract.payments:
        payment.append("Төлем кестесі осы келісімшарттың қосымшасында көрсетілген.")
    payment.append(
        "Төлем мерзімі өткен жағдайда берешек Жатақхананың есеп жүйесінде «мерзімі "
        "өтті» деп белгіленеді, ал Тұрғын оны бірінші талап бойынша өтеуге міндетті."
    )

    return [
        (
            "Келісімшарттың мәні",
            [
                f"{place}, ал Тұрғын оны осы келісімшарт талаптарына сай пайдаланып, "
                "тұру ақысын уақытылы төлеуге міндеттенеді.",
                f"Тұру мерзімі: {format_date(contract.start_date)} – "
                f"{format_date(contract.end_date)}.",
                "Төсек-орын тек Тұрғынның жеке тұруына арналған және оны басқа "
                "адамдарға беруге болмайды.",
            ],
        ),
        ("Төлем мөлшері мен тәртібі", payment),
        (
            "Жатақхананың міндеттері",
            [
                "Тұрғынға санитарлық және өрт қауіпсіздігі талаптарына сай төсек-орын "
                "беру.",
                "Бөлмені жиһазбен және төсек жабдықтарымен қамтамасыз ету.",
                "Жылу, электр және сумен жабдықтау жүйелерінің жұмысын қамтамасыз ету, "
                "ақауларды ақылға қонымды мерзімде жою.",
                "Тұрғынды жатақхананың ішкі тәртіп ережелерімен таныстыру.",
            ],
        ),
        (
            "Тұрғынның міндеттері",
            [
                "Жатақхананың ішкі тәртіп ережелерін, өрт қауіпсіздігі және "
                "санитарлық талаптарды сақтау.",
                "Тұру ақысын осы келісімшартта белгіленген мөлшерде және мерзімде "
                "төлеу.",
                "Жатақхана мүлкіне ұқыпты қарау, бөлме мен ортақ пайдаланылатын "
                "орындарды таза ұстау.",
                "Өзі келтірген материалдық залалды толық көлемде өтеу.",
                "Сағат 23:00-ден 07:00-ге дейін тыныштық сақтау.",
                "Келісімшарт мерзімі аяқталғанда немесе ол бұзылғанда бөлмені үш "
                "күнтізбелік күн ішінде босатып, мүлікті бастапқы күйінде тапсыру.",
            ],
        ),
        (
            "Келісімшартты өзгерту және бұзу",
            [
                "Келісімшартқа өзгерістер Тараптардың жазбаша келісімімен енгізіледі.",
                "Тұрғын кемінде 10 күнтізбелік күн бұрын жазбаша ескертіп, "
                "келісімшартты мерзімінен бұрын бұзуға құқылы.",
                "Жатақхана келісімшартты біржақты тәртіппен мына жағдайларда бұзуға "
                "құқылы: тұру ақысы екі айдан астам төленбесе; ішкі тәртіп ережелері "
                "өрескел немесе бірнеше рет бұзылса; Тұрғын оқудан шығарылса.",
            ],
        ),
        (
            "Қорытынды ережелер",
            [
                "Келісімшарт Тараптар қол қойған күннен бастап күшіне енеді және "
                "1.2-тармақта көрсетілген мерзім аяқталғанға дейін қолданылады.",
                "Даулар келіссөздер арқылы, ал келісімге келмеген жағдайда Қазақстан "
                "Республикасының заңнамасына сәйкес шешіледі.",
                "Келісімшарт заңдық күші бірдей екі данада, әр Тарапқа бір-бірден "
                "жасалды.",
            ],
        ),
    ]


class ContractDocument(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_margins(22, 20, 22)
        self.set_auto_page_break(True, margin=22)
        self.add_font(FONT, "", str(FONT_DIR / "DejaVuSerif.ttf"))
        self.add_font(FONT, "B", str(FONT_DIR / "DejaVuSerif-Bold.ttf"))
        self.set_lang("kk")

    def footer(self):
        self.set_y(-14)
        self.set_font(FONT, "", 8)
        self.set_text_color(120)
        self.cell(0, 5, f"{self.page_no()} / {{nb}}", align="C")
        self.set_text_color(0)

    def paragraph(self, text, style="", size=10.5, align="J", gap=2.2):
        self.set_font(FONT, style, size)
        self.multi_cell(0, 5.6, text, align=align, new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)


def render_contract_pdf(contract):
    """Return the agreement for `contract` as PDF bytes."""
    student = contract.student
    pdf = ContractDocument()
    pdf.set_title(contract_title(contract).replace("\n", " "))
    pdf.set_author(DORMITORY)
    pdf.add_page()

    pdf.paragraph(contract_title(contract), style="B", size=13, align="C", gap=1)
    pdf.paragraph(long_date(signing_date(contract)), align="C", gap=5)
    pdf.paragraph(contract_preamble(contract), gap=4)

    for number, (heading, clauses) in enumerate(contract_sections(contract), 1):
        if pdf.will_page_break(24):
            # Never leave a heading alone at the foot of a page.
            pdf.add_page()
        pdf.paragraph(f"{number}. {heading}", style="B", size=11, align="L", gap=1)
        for index, clause in enumerate(clauses, 1):
            pdf.paragraph(f"{number}.{index}. {clause}", gap=1)
        pdf.ln(2.5)

    # Details and signatures of both parties, side by side.
    heading_number = len(contract_sections(contract)) + 1
    if pdf.will_page_break(60):
        pdf.add_page()
    pdf.paragraph(
        f"{heading_number}. Тараптардың деректемелері мен қолдары",
        style="B",
        size=11,
        align="L",
        gap=2,
    )
    column = (pdf.w - pdf.l_margin - pdf.r_margin - 10) / 2
    top = pdf.get_y()
    parties = (
        ("Жатақхана", [DORMITORY, "Жатақхана әкімшілігі"]),
        (
            "Тұрғын",
            [student.full_name, student.email, student.phone or "телефон көрсетілмеген"],
        ),
    )
    bottom = top
    for position, (role, lines) in enumerate(parties):
        left = pdf.l_margin + position * (column + 10)
        pdf.set_xy(left, top)
        pdf.set_font(FONT, "B", 10.5)
        pdf.multi_cell(column, 5.6, role, new_x="LEFT", new_y="NEXT")
        pdf.set_font(FONT, "", 10)
        for line in lines:
            pdf.set_x(left)
            pdf.multi_cell(column, 5.2, line, new_x="LEFT", new_y="NEXT")
        bottom = max(bottom, pdf.get_y())
    for position in range(2):
        left = pdf.l_margin + position * (column + 10)
        pdf.set_xy(left, bottom + 12)
        pdf.set_font(FONT, "", 10)
        pdf.multi_cell(column, 5.2, "Қолы: ______________________")
    pdf.set_y(bottom + 22)

    if contract.payments:
        pdf.add_page()
        pdf.paragraph("Қосымша. Төлем кестесі", style="B", size=11, align="L", gap=1)
        pdf.paragraph(
            f"№ {contract.number} келісімшарт бойынша, тұрғын: {student.full_name}.",
            gap=3,
        )
        pdf.set_font(FONT, "", 10)
        with pdf.table(
            width=120,
            align="LEFT",
            col_widths=(14, 53, 53),
            text_align=("CENTER", "LEFT", "RIGHT"),
            line_height=7,
        ) as table:
            header = table.row()
            for title in ("№", "Төлеу мерзімі", "Сома"):
                header.cell(title)
            for index, payment in enumerate(contract.payments, 1):
                row = table.row()
                row.cell(str(index))
                row.cell(format_date(payment.due_date))
                row.cell(tenge(payment.amount))
        pdf.ln(3)
        pdf.paragraph(f"Барлығы: {tenge(contract.total_due)}.", style="B", align="L")

    return bytes(pdf.output())
