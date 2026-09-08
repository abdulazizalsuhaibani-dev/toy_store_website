# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Django 5.0 toy store website. Single Django app (`apps/toymodule`) providing a product catalog (browsable by category), user registration/login, and a dashboard for adding products.

## Commands

The environment is managed with [uv](https://docs.astral.sh/uv/); the venv lives at `.venv/`. `Pillow` is a hard requirement (Django refuses to start without it because `Product.pimage` is an `ImageField`).

```bash
# First-time setup
uv venv --python 3.12
uv pip install -r requirements.txt
cp .env.example .env   # then fill in DJANGO_SECRET_KEY
python manage.py migrate   # db.sqlite3 is not in the repo; this creates it

# Run the dev server
python manage.py runserver

# Make/apply migrations after changing apps/toymodule/models.py
python manage.py makemigrations
python manage.py migrate

# Create an admin user (needed to reach /dashboard and /addProduct, which require login)
python manage.py createsuperuser

# Run tests (CI invokes this; no tests currently exist in the repo)
python manage.py test

# Production checks. CI runs both; they exercise the DEBUG=False branch of
# settings.py, which is otherwise never hit locally.
DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=example.com python manage.py check --deploy --fail-level WARNING
python manage.py collectstatic --no-input

# Push local media/ into the configured remote storage (one-time, at deploy).
python manage.py upload_media --dry-run
```

Database is SQLite (`db.sqlite3`), gitignored and not shipped with a clone — run `migrate` to create it. Uploaded product images are written under `media/` (served via `MEDIA_URL`/`MEDIA_ROOT` in `toystorewebsite/settings.py`); `media/` is gitignored, so new uploads stay out of this public repo while the demo images already tracked there remain. Static assets referenced in templates live under `static/`.

## Architecture

- **`toystorewebsite/`** — the Django project package: `settings.py`, root `urls.py` (mounts `admin/` and delegates everything else to `apps.toymodule.urls`), `wsgi.py`/`asgi.py`.
- **`apps/toymodule/`** — the single Django app holding all business logic:
  - `models.py` — one model, `Product` (`pname`, `pimage`, `pprice`, `pcategory`). There is no `Category` model; categories are plain strings on `Product` (e.g. `"Baby Toys"`, `"Outdoors"`, `"Dolls and Playsets"`, `"Cars and Bikes"`, default `"Others"`). Category browse views filter on `pcategory__exact`, so a view and the category string stored on products must match exactly.
  - `views.py` — function-based views only (no CBVs, no DRF/API layer). Category pages (`babyToys`, `outdoors`, `dollsAndPlaysets`, `carsAndBikes`) each hardcode their `pcategory` filter string. `dashboard`, `accountInfo`, and `addProduct` are gated with `@login_required(login_url='login')`.
  - `forms.py` — `AddProductForm` (ModelForm over `Product`, all fields), `AddUserForm` (extends `UserCreationForm`), `LoginForm` (extends `AuthenticationForm`). Auth is Django's built-in `django.contrib.auth` — no custom User model.
  - `urls.py` — all app routes, plus the `static()` helper appended to serve `MEDIA_URL` in development.
  - `admin.py` — registers `Product` with the default admin.
- **`apps/templates/`** — the single template root (`TEMPLATE_DIR` in `settings.py`, `APP_DIRS` also on). `layouts/base.html` is the shared layout; `includes/` holds `header.html`/`footer.html`/`sidebar.html` partials; `toymodule/` holds the page templates. When adding a page, extend `layouts/base.html` and add a template under `apps/templates/toymodule/`.
- Styling uses Bootstrap 5 via `django-crispy-forms` + `crispy-bootstrap5` (`CRISPY_TEMPLATE_PACK = "bootstrap5"` in settings) — render forms in templates with `{{ form|crispy }}` rather than hand-rolled `<form>` markup.
- `apps` is a Django namespace package (no `apps/__init__.py`) — this is intentional for Django 5, not an oversight.
- **Deployment** — `render.yaml` (Render Blueprint), `build.sh` (install → `collectstatic` → `migrate` → optional first superuser), `.python-version`, and `DEPLOYMENT.md` (the runbook, including the Supabase gotchas). Target is a free Render web service with Postgres and uploaded images on Supabase; `apps/toymodule/management/commands/upload_media.py` does the one-time push of `media/` into the bucket. Free Render instances have no persistent disk, which is why neither the database nor uploads may live on them.

## Notes for changes

- `SECRET_KEY` is read from `DJANGO_SECRET_KEY` (loaded from a gitignored `.env`). If it's unset, startup raises `ImproperlyConfigured` when `DEBUG` is off, and under `DEBUG` falls back to a throwaway key generated per process with a `RuntimeWarning` — so a fresh clone still runs, but sessions reset on every restart until `.env` is filled in. CI supplies the key explicitly.
- `DEBUG` comes from `DJANGO_DEBUG` and **defaults to `False`**, so a deployed host that is missing the variable fails safe. Local development sets `DJANGO_DEBUG=True` in `.env` — a clone without one will start in production mode and refuse to run without a secret key. Everything under `if not DEBUG:` in `settings.py` (HTTPS redirect, secure cookies, HSTS) is off locally by design.
- Deployment settings are all env-driven with local fallbacks, so `runserver` and `manage.py test` need no configuration: no `DATABASE_URL` means SQLite, no `SUPABASE_S3_ENDPOINT` means local file storage. This is deliberate — one settings module, no `settings/prod.py` split, and CI exercises the same file production does.
- This repo is **public**, and `db.sqlite3` remains in git history (with four demo accounts' emails and pbkdf2 password hashes) even though it's no longer tracked. The original `SECRET_KEY` is likewise still in history and has been rotated, so the leaked one is worthless. Don't commit real credentials or user data here.
- Adding a new product category means updating both the string used when filtering in a new/existing view and wherever the category is presented for selection (there's no shared choices list — `AddProductForm`'s commented-out `CATEGORIES_CHOICES` was never wired in, so `pcategory` is currently just a free-text `CharField`).
