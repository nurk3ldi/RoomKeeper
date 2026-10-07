# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

RoomKeeper is a university coursework project (СӨЖ — student independent work), **variant 2: "Dormitory Manager"** — a web app for managing dormitory places. The user communicates in Kazakh; reply in Kazakh.

Variant specifics:

- Models: `Student`, `Room`, `Payment`/`Contract`
- Features: room occupancy calculation, payment status
- File upload: contract PDF

Deadline: week 7–8 of the semester.

## Current status

**Keep this section up to date** — at the end of each working session, record what was done and what comes next, so the next session knows where the project stands.

- 2026-10-07 (session 1): Scaffold only; assignment requirements recorded here.
- 2026-10-07 (session 2): **All 11 mandatory requirements are implemented.** Decided with the user: UI is Jinja2 only (the React `web/` folder was deleted) and everything stays under `server/`. Built models, auth + roles, CRUD for rooms/students/contracts/payments, search/filter/sort/pagination, contract PDF upload, error pages, JSON API, CLI (`seed`, `create-admin`), pytest suite, Kazakh `README.md`, Postman collection and 10 screenshots in `docs/`. The local PostgreSQL database has tables and demo data loaded.
- 2026-10-08 (session 3): Work committed to `main` as `d170dc8` (`CLAUDE.md` deliberately left out of git — publishing it is the user's call). `git push` failed in-session: no GitHub credentials available here, the user has to push. Then added **Flask-Migrate**: `server/migrations/` with the initial revision `265c8d51b46b` (a second revision, `21ca46c53f9f`, later made `students.phone`/`course` nullable); the old `init-db` command was removed in favour of `flask db upgrade`. The local PostgreSQL database was stamped at head. The migration work is **not committed yet**.
- 2026-10-08 (session 3, later): Added a public **home page** at `/` (`main.home`, `templates/main/home.html`); the dashboard moved to `/dashboard`. After trying a navy/amber and a navy/coral scheme, the user settled on the **indigo-lavender palette**: off-white `#F7F7FB` background, indigo-navy `#1B1B3A` structure/text, violet `#6C5CE7` accent — do not swap it for another scheme unasked. Screenshots in `docs/screenshots/` were retaken. Also not committed yet.
- 2026-10-08 (session 3, last): The home page was rebuilt after the user's reference (`home_reference.png` in the repo root — a third-party landing page screenshot, kept untracked, not for committing) and then trimmed on request to a single screen: header and dotted background span 100% of the window while the content stays on the standard 1120px column (`.topbar-inner`, `.lp-stage`) — the user asked for exactly this split, key tile + two-line headline, four tilted corner widgets (occupancy ring, contract sheet, per-floor bars, residents card with anonymous avatars). Not committed yet.
- Possible next steps (none required by the assignment): record the optional 2–3 minute demo video (script is in `README.md`), push to GitHub and put the real repository URL into the README's `git clone` line, retake screenshots if the UI changes.

## Assignment requirements (mandatory)

Stack: Python 3.x, Flask, Flask-SQLAlchemy, Jinja2, SQLite or PostgreSQL.

1. Register / login / logout (session or Flask-Login).
2. At least 2 roles: `admin` and `user` (admin has broader management rights).
3. At least 3 tables with a relationship (one-to-many or many-to-many).
4. Full CRUD in the main section.
5. Search and filter/sort on at least one page.
6. Pagination on at least one list page.
7. Form validation (required fields, length, numeric range, email/phone, etc.).
8. File upload: image or PDF/document, with safe filename and extension check.
9. Custom error pages for 404 and 500.
10. API: at least 3 endpoints (GET/POST/PUT or DELETE).
11. README: install, run, DB migration/initialisation, test accounts, screenshots.

Required structure: `app/` (blueprints recommended), `templates/`, `static/`, `models.py`, `routes.py`, `forms.py` (if used), `config.py`, `.env` for secrets, `.gitignore`.

### Grading (100 points)

| Criterion | Points |
| --- | --- |
| Architecture and code quality (blueprints, structure, DRY) | 15 |
| DB models and relationships (3+ tables) | 15 |
| Auth + role-based access (admin/user) | 15 |
| CRUD complete and working | 15 |
| Search + filter/sort + pagination | 10 |
| Form validation + security (input sanitation, upload check) | 10 |
| File upload and storage logic | 5 |
| API endpoints (3+) and tests (Postman collection is a plus) | 10 |
| UI (Jinja2 templates, navigation, flash messages) | 3 |
| README + screenshots + demo scenario | 2 |

Deliverables: GitHub repository link, `README.md`, 6–10 screenshots, optional 2–3 minute demo video (bonus).

## Layout

One Flask app, in `server/` (run everything from that directory):

- `run.py` — entry point; `config.py` — settings read from `server/.env`
- `app/__init__.py` — `create_app()` and the extensions `db`, `login_manager`, `csrf`
- `app/models.py` — `User`, `Room`, `Student`, `Contract`, `Payment`
- `app/forms.py` — all Flask-WTF forms and validators
- `app/<blueprint>/routes.py` — blueprints `main`, `auth`, `rooms`, `students`, `contracts`, `payments`, `users`, `api`
- `app/utils.py` (role decorator, pagination, sorting, upload helpers), `app/services.py` (stats), `app/errors.py`, `app/cli.py`, `app/template_helpers.py`
- `app/templates/`, `app/static/css/style.css` — Jinja2 UI, hand-written CSS, no CDN or JS build. All colours are CSS variables in `:root`; green/amber/red are reserved for statuses (`--success`, `--warning`, `--danger`), so keep brand colours (`--primary`, `--accent`) out of status badges. The header is white and the page background is the dotted cool grey (`--bg` plus a radial-gradient on `body`) on every page — the user asked for the home page's header and background everywhere
- `uploads/contracts/` — uploaded PDFs (git-ignored)
- `migrations/` — Alembic revisions (Flask-Migrate); the directory is passed to `Migrate` as an absolute path
- `tests/` — pytest suite
- `../docs/` — Postman collection and README screenshots

## Commands

All from `server/` with the venv active (`source .venv/bin/activate`):

```bash
pip install -r requirements.txt        # requirements-dev.txt adds pytest
cp .env.example .env                   # then fill in SECRET_KEY and DATABASE_URL
flask --app run db upgrade             # apply migrations (creates the tables)
flask --app run seed                   # demo data; refuses if users already exist
flask --app run db migrate -m "..."    # after changing models.py: generate a revision, review it, then upgrade
flask --app run db downgrade base      # drop every table (reset: downgrade base, upgrade, seed)
python run.py                          # dev server with debug on, http://localhost:5000
python -m pytest                       # whole suite
python -m pytest tests/test_rooms.py -k pagination   # a single test
```

Demo accounts after `seed`: `admin` / `Admin123!` (admin) and `miras` / `User123!` (a student's account). The user asked for exactly these two — do not add more demo accounts.

There is no linter. Schema changes go through Flask-Migrate (Alembic) in `server/migrations/`: every change to `models.py` needs a new revision, and `tests/test_migrations.py` fails if the migrations and the models drift apart. Only the tests use `db.create_all()`. Autogenerate a revision against a database that is at the previous head (not one built by `create_all`), otherwise the diff comes out empty.

## Architecture

- **Language**: UI text and README are in Kazakh; code, identifiers and comments are in English.
- **Config**: `config.py` reads `SECRET_KEY` and `DATABASE_URL` with `os.environ[...]`, so the app fails at import with a `KeyError` if either is missing. `create_app(config_class)` accepts another config class; the tests pass one that uses in-memory SQLite, so models and queries must stay portable between PostgreSQL and SQLite.
- **Roles**: `admin_required` in `app/utils.py` wraps `login_required` and aborts with 403. The home page `/` is public and must only show aggregate occupancy numbers (no names, no payment data). `user` accounts can only see the dashboard, the rooms list/detail (without resident names) and their own profile. Registration creates the account's `Student` record at once (`Student.link_account`): the form asks for the full name, and `phone`/`course` stay empty (nullable) until an admin fills them in. If an admin already entered a student with the same email and it has no account yet, sign-up claims that record instead of creating a second one — the user asked for accounts to be linked automatically; the email is not verified, which is an accepted trade-off for this coursework. An admin can still re-link accounts in the student form (`Student.user_id`).
- **Occupancy**: `Room.occupied` is a `column_property` (correlated `COUNT` over students), so it can be used in `WHERE`/`ORDER BY`. It is loaded with the row and goes stale until the session is committed or the row is refreshed.
- **Payment status** is not stored: `Payment.status` derives it from `paid_at` and `due_date`, and `Payment.status_filter()` is the matching SQL expression — change both together. Same pairing for `Contract.state` / `Contract.state_filter()`.
- **Forms**: every form extends `BaseForm`, which keeps the edited row in `form.obj` so the `Unique` validator and "room is full" check can ignore the row's own values. Select fields use `0` for "none". The API validates room JSON through the same `RoomForm` (`room_form()` in `app/api/routes.py`).
- **Lists**: `apply_sort()` only accepts keys from each view's `SORT_COLUMNS` whitelist; `paginate()` fixes `per_page` from `ITEMS_PER_PAGE`. Templates build sort/page links with the `list_url` macro, which preserves the current query string.
- **Uploads**: `ContractForm.validate_pdf` checks extension and the `%PDF-` signature; `save_contract_pdf()` stores the file under a random UUID name and keeps a sanitised display name. Files are served only by `contracts.download` (admin or the contract's owner). Files are deleted from disk after the DB commit that drops or replaces them.
- **CSRF**: `CSRFProtect` covers all HTML forms; state-changing actions are POST-only via the `post_button` macro. The `api` blueprint is exempt and relies on the `SameSite=Lax` session cookie.
- **Errors**: `app/errors.py` returns JSON for any path under `/api/` and HTML otherwise. Error templates extend the standalone `errors/layout.html` (not `base.html`) so they render even when the database is down.
- **Home page**: `templates/main/home.html` overrides the `topbar_nav`, `main` and `footer` blocks of `base.html`. By the user's request it is a single screen: no scrolling (`.page-home` is exactly one viewport high and the hero takes the remaining height), no section menu in the header (only a text link plus an outlined button: login/register, or logout/dashboard), no lead text, CTA button, feature sections or footer. Animations are entrance-only CSS keyframes that animate `translate`/`scale`/`opacity`, so each widget keeps its own `rotate`; nothing moves after it has appeared — do not add looping motion. The four corner widgets are `aria-hidden` decoration, hidden below 1020px width (and the lower pair below 640px height). Flash messages render in `.flash-area` between the topbar and the `main` block.
- **Auth pages**: `auth/login.html` and `auth/register.html` extend `auth/_layout.html` and only fill the `heading`, `fields` and `submit` blocks. The user asked for them to be minimal, in the home page style: a single white card (the `<form class="auth-card">` itself) that holds the logo tile, the two-tone headline, placeholder-only inputs (`ui.field(..., compact=true)` keeps the label for screen readers) and a single button. Password inputs get a show/hide button from the `field` macro (any `PasswordField`); it is wired by `static/js/password-toggle.js`, the project's only script, loaded only on the auth pages. The button is `hidden` in the markup and revealed by the script, and the field is switched back to `type=password` on submit. Otherwise: no hints, no "remember me", no cross-links (the header already has both) and no footer. Keep additions out of these pages.
- **Account controls**: for a logged-in user the header shows only a round profile icon (`ui.profile_link()`, the name and role are in its tooltip). Logging out is done from the profile page (`Жүйеден шығу` in its page head) — the user asked for it to live there, so do not put a log-out control back in the header.
- **Templates**: import shared macros with `{% import "_macros.html" as ui with context %}` — `with context` is required because the macros use `current_user` and the label dictionaries injected by `template_helpers.py`.
- **Tests**: never hold an app context open across `client` requests (Flask-Login caches the user on `g`); create data through the `make` fixture, which commits in its own context and returns ids.
