# Toy Store

A toy store web application built with Django 5 — a product catalogue browsable
by category, user registration and login, and a dashboard for adding products.

[![Django CI](https://github.com/abdulazizalsuhaibani-dev/toy_store_website/actions/workflows/django.yml/badge.svg)](https://github.com/abdulazizalsuhaibani-dev/toy_store_website/actions/workflows/django.yml)

**Live demo: https://toy-store-website.onrender.com**

> Hosted on free tiers, so the first request after a quiet spell takes about a
> minute while the instance wakes up.

## Features

- Product catalogue with per-category browsing — Baby Toys, Cars and Bikes,
  Dolls and Playsets, Outdoors
- Registration, login and logout on Django's built-in auth
- Login-gated dashboard for adding products, with image upload
- Bootstrap 5 styling through `django-crispy-forms`
- Django admin at `/admin` for direct catalogue management

## Tech stack

| | |
|---|---|
| Framework | Django 5.0 |
| Database | SQLite locally, PostgreSQL in production |
| Forms/UI | django-crispy-forms + crispy-bootstrap5, Bootstrap 5 (Bootswatch Cerulean) |
| Images | Pillow; local filesystem locally, S3-compatible object storage in production |
| Serving | gunicorn + WhiteNoise |
| Hosting | Render (web service) + Supabase (Postgres and Storage) |

## Getting started

Requires Python 3.10+ (3.12 recommended). The project uses
[uv](https://docs.astral.sh/uv/), though plain `venv` and `pip` work too.

```bash
git clone git@github.com:abdulazizalsuhaibani-dev/toy_store_website.git
cd toy_store_website

uv venv --python 3.12
uv pip install -r requirements.txt

cp .env.example .env      # then fill in DJANGO_SECRET_KEY, keep DJANGO_DEBUG=True
python manage.py migrate  # db.sqlite3 is not in the repo; this creates it
python manage.py createsuperuser
python manage.py runserver
```

Then open http://127.0.0.1:8000.

`.env` matters: `DJANGO_DEBUG` defaults to **False** so that a deployed host
missing the variable fails safe rather than serving debug pages, and with debug
off a missing `DJANGO_SECRET_KEY` is a hard error. A clone without a filled-in
`.env` will refuse to start.

## Configuration

Everything deployment-specific is read from the environment and falls back to
the local setup when unset, so there is one settings module rather than a
`settings/prod.py` split — and CI exercises the same file production does.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Required. Throwaway per-process key under `DEBUG` only. |
| `DJANGO_DEBUG` | `False` | Set `True` for local development. |
| `DJANGO_ALLOWED_HOSTS` | — | Comma-separated. Render's own hostname is added automatically. |
| `DATABASE_URL` | — | Unset → SQLite. Set → PostgreSQL. |
| `SUPABASE_S3_*` | — | Unset → uploads go to `media/`. Set → uploads go to the bucket. |

See [`.env.example`](.env.example) for the full list.

## Project layout

```
apps/toymodule/      the single Django app — models, views, forms, urls
  management/        upload_media, for pushing media/ into remote storage
apps/templates/      layouts/, includes/ partials, and toymodule/ page templates
toystorewebsite/     project package — settings, root urls, wsgi/asgi
static/              static assets (collected to staticfiles/ at build time)
media/               uploaded product images (local development)
```

`Product` is the only model: `pname`, `pimage`, `pprice`, `pcategory`. There is
no `Category` model — categories are plain strings on `Product`, and each
category view filters on an exact match, so a new category means updating both
the view and wherever the category is offered for selection.

## Development

```bash
python manage.py test                    # test runner (no tests written yet)
python manage.py makemigrations          # after changing models.py
python manage.py migrate

# Production checks — these exercise the DEBUG=False branch of settings.py,
# which local development never reaches. CI runs both on every push.
DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=example.com \
  python manage.py check --deploy --fail-level WARNING
python manage.py collectstatic --no-input
```

## Deployment

Deploys to Render from `render.yaml`, with PostgreSQL and uploaded images on
Supabase. Push to `main` triggers a build.

**[DEPLOYMENT.md](DEPLOYMENT.md)** is the full runbook. It is worth reading
before deploying rather than after — it covers the failures that only show up
in production, including Supabase's IPv6-only direct connection (unreachable
from Render), the HTTPS redirect loop behind Render's TLS-terminating proxy,
and revoking the PostgREST grants that would otherwise leave Django's
`auth_user` and `django_session` tables readable over Supabase's REST API.

## Licence

No licence has been specified for this project.
