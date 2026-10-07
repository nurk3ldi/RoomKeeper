from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app import db
from app.forms import StudentForm
from app.models import Room, Student
from app.students import bp
from app.utils import admin_required, apply_sort, delete_contract_pdf, paginate

SORT_COLUMNS = {
    "name": Student.full_name,
    "course": Student.course,
    "created": Student.created_at,
}


def save_student(student, form):
    student.full_name = form.full_name.data
    student.email = form.email.data
    student.phone = form.phone.data
    student.course = form.course.data
    # 0 is the "none" option of both selects.
    student.room_id = form.room_id.data or None
    student.user_id = form.user_id.data or None


@bp.get("/")
@admin_required
def index():
    query = select(Student).options(joinedload(Student.room))

    q = request.args.get("q", "").strip()
    if q:
        query = query.where(
            or_(
                Student.full_name.icontains(q, autoescape=True),
                Student.email.icontains(q, autoescape=True),
                Student.phone.contains(q, autoescape=True),
            )
        )

    room = request.args.get("room", "")
    if room == "none":
        query = query.where(Student.room_id.is_(None))
    elif room.isdigit():
        query = query.where(Student.room_id == int(room))

    course = request.args.get("course", type=int)
    if course is not None:
        query = query.where(Student.course == course)

    query, sort, order = apply_sort(query, SORT_COLUMNS, "name")
    rooms = db.session.scalars(select(Room).order_by(Room.number)).all()
    return render_template(
        "students/list.html",
        page=paginate(query.order_by(Student.id)),
        rooms=rooms,
        q=q,
        room=room,
        course=course,
        sort=sort,
        order=order,
    )


@bp.get("/<int:student_id>")
@admin_required
def detail(student_id):
    student = db.get_or_404(Student, student_id)
    return render_template("students/detail.html", student=student)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    form = StudentForm(room_id=request.args.get("room_id", type=int))
    if form.validate_on_submit():
        student = Student()
        save_student(student, form)
        db.session.add(student)
        db.session.commit()
        flash(f"{student.full_name} қосылды.", "success")
        return redirect(url_for("students.detail", student_id=student.id))
    return render_template("students/form.html", form=form, student=None)


@bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(student_id):
    student = db.get_or_404(Student, student_id)
    form = StudentForm(obj=student)
    if form.validate_on_submit():
        save_student(student, form)
        db.session.commit()
        flash(f"{student.full_name} деректері жаңартылды.", "success")
        return redirect(url_for("students.detail", student_id=student.id))
    return render_template("students/form.html", form=form, student=student)


@bp.post("/<int:student_id>/delete")
@admin_required
def delete(student_id):
    student = db.get_or_404(Student, student_id)
    name = student.full_name
    pdf_files = [contract.pdf_filename for contract in student.contracts]
    db.session.delete(student)
    db.session.commit()
    # Files go only after the rows are really gone.
    for pdf_file in pdf_files:
        delete_contract_pdf(pdf_file)
    flash(f"{name} және оның келісімшарттары өшірілді.", "success")
    return redirect(url_for("students.index"))
