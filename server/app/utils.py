from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from flask import abort, current_app, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db

PDF_SIGNATURE = b"%PDF-"


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def paginate(query):
    per_page = current_app.config["ITEMS_PER_PAGE"]
    return db.paginate(query, per_page=per_page, max_per_page=per_page, error_out=False)


def apply_sort(query, columns, default):
    """Order `query` by the whitelisted column named in ?sort=&order=."""
    key = request.args.get("sort", default)
    if key not in columns:
        key = default
    order = "desc" if request.args.get("order") == "desc" else "asc"
    column = columns[key]
    return query.order_by(getattr(column, order)()), key, order


def safe_next_url(default):
    """Return ?next= only if it points back into this site."""
    target = request.args.get("next", "")
    parts = urlsplit(target)
    if target.startswith("/") and not target.startswith("//") and not parts.netloc:
        return target
    return default


def has_allowed_extension(filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return extension in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]


def looks_like_pdf(file_storage):
    head = file_storage.stream.read(len(PDF_SIGNATURE))
    file_storage.stream.seek(0)
    return head == PDF_SIGNATURE


def save_contract_pdf(file_storage):
    """Store an already validated PDF; return (stored_name, display_name).

    The file is saved under a random name, so nothing from the client ends
    up in the path. The sanitised original name is kept only for downloads.
    """
    display_name = secure_filename(file_storage.filename)
    if not has_allowed_extension(display_name):
        # secure_filename drops non-ASCII letters, e.g. "келісім.pdf" -> "pdf".
        display_name = "contract.pdf"
    stored_name = f"{uuid4().hex}.pdf"
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    file_storage.save(folder / stored_name)
    return stored_name, display_name


def delete_contract_pdf(stored_name):
    if stored_name:
        path = Path(current_app.config["UPLOAD_FOLDER"]) / stored_name
        path.unlink(missing_ok=True)
