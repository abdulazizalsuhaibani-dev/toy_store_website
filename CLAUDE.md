# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Django 5.0 toy store website. Single Django app (`apps/toymodule`) providing a product catalog (browsable by category), user registration/login, and a dashboard for adding products.

## Commands

There is no `requirements.txt` in the repo (the CI workflow at `.github/workflows/django.yml` expects one at the root but it's missing — create it with `pip freeze > requirements.txt` from a working environment before relying on CI or a fresh install). Known direct dependencies from `settings.py`/imports: `django`, `django-crispy-forms`, `crispy-bootstrap5`.

```bash
# Run the dev server
python manage.py runserver

# Make/apply migrations after changing apps/toymodule/models.py
python manage.py makemigrations
python manage.py migrate

# Create an admin user (needed to reach /dashboard and /addProduct, which require login)
python manage.py createsuperuser

# Run tests (CI invokes this; no tests currently exist in the repo)
python manage.py test
```

Database is SQLite (`db.sqlite3`, committed to the repo). Uploaded product images are written under `media/` (served via `MEDIA_URL`/`MEDIA_ROOT` in `toystorewebsite/settings.py`), and static assets referenced in templates live under `static/`.

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

## Notes for changes

- `DEBUG = True` and a hardcoded `SECRET_KEY` are committed in `toystorewebsite/settings.py` — this is a dev-only configuration, not something to "fix" incidentally while working on unrelated tasks.
- Adding a new product category means updating both the string used when filtering in a new/existing view and wherever the category is presented for selection (there's no shared choices list — `AddProductForm`'s commented-out `CATEGORIES_CHOICES` was never wired in, so `pcategory` is currently just a free-text `CharField`).
