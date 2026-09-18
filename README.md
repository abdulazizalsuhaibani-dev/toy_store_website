# Toy Store

A toy store web application built with Django 5 — a bilingual (English/Arabic)
product catalogue browsable by category, search with filters, a cart and
checkout, user registration and login, and a dashboard for adding products.

The storefront implements the **Happybox** design from Claude Design
(project `56e1a170`): flat ink outlines, hard offset shadows, Baloo 2 display
type, and a five-colour category palette. `static/css/happybox.css` is that
design system; the page templates compose it.

[![Django CI](https://github.com/abdulazizalsuhaibani-dev/toy_store_website/actions/workflows/django.yml/badge.svg)](https://github.com/abdulazizalsuhaibani-dev/toy_store_website/actions/workflows/django.yml)

**Live demo: https://toy-store-website.onrender.com**

> Hosted on free tiers, so the first request after a quiet spell takes about a
> minute while the instance wakes up.

## Features

- Product catalogue with per-category browsing, driven by a `Category` model —
  a new shelf is a row, not a new view
- Product detail pages with age range, piece count, play type and ratings
- Search with age, category and price filters, and three sort orders
- Cart and checkout: quantities, gift wrap, three delivery options, and an
  `Order` record. **No payment processor** — the card fields on the checkout
  screen are inert and nothing is charged or stored
- Bilingual English/Arabic with full RTL, toggled in the header
- Seven-currency picker (the Gulf pegs plus USD), with prices stored once in a
  base currency and converted for display
- Registration, login and logout on Django's built-in auth; a signed-out cart
  is adopted on sign-in
- Login-gated dashboard for adding products and reviewing your own orders
- Django admin at `/admin` for direct catalogue management

## Tech stack

| | |
|---|---|
| Framework | Django 5.0 |
| Database | SQLite locally, PostgreSQL in production |
| Forms | django-crispy-forms + crispy-bootstrap5 |
| UI | `static/css/happybox.css` — hand-written; no CSS framework. It also styles the crispy `bootstrap5` class names, since the pack emits them and Bootstrap is no longer loaded |
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
python manage.py seed_catalog   # optional: the eight demo toys from the design
python manage.py createsuperuser
python manage.py runserver
```

`migrate` also seeds the reference data the storefront cannot run without —
categories, currencies and delivery options — because a shop with no currency
cannot print a price and a checkout with no delivery option cannot be
completed. Products are *not* seeded by `migrate`; `seed_catalog` is opt-in and
matches on slug, so it never duplicates and never touches rows it did not
create.

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

### Models

| Model | What it holds |
|---|---|
| `Category` | A shelf: name (+ Arabic), slug, colour, glyph, blurb. Replaced the free-text `Product.pcategory` string. |
| `Product` | `pname`/`pimage`/`pprice` keep their original names; plus Arabic name and blurb, age range, badge, pieces, play type, rating, review count, card colour, stock and featured flags. |
| `Currency` | The design's seven currencies. `rate` is units per USD; exactly one row is `is_base`, and that is the currency `Product.pprice` is stored in (SAR). |
| `DeliveryOption` | The checkout's three delivery speeds, with a free-over threshold. |
| `Cart` / `CartItem` | A toy box in progress, keyed by session and adopted by the account on sign-in. |
| `Order` / `OrderItem` | A placed order. Lines snapshot name and price, so a later rename or reprice cannot rewrite an old receipt. |

Prices are stored once, in the base currency, and converted at render time —
an order additionally records the currency code the shopper agreed the total
in, so a receipt never silently re-prices itself.

Migration `0016` adds the schema, `0017` backfills it and maps every existing
`pcategory` string onto a `Category` row, and `0018` drops the old column. They
are split because each step is only safe once the previous one has run.

### Copy and localisation

`apps/toymodule/strings.py` holds every UI string as an `(English, Arabic)`
pair, flattened per request into `{{ t.someKey }}`. It is a dict rather than a
gettext catalogue because the site is two languages chosen by a header toggle,
not by `Accept-Language`. Model-side copy lives in `*_ar` columns. Swap both
for gettext / django-parler the day a third language appears.

The staff-facing pages (`/addProduct`, `/dashboard`) use the storefront chrome
but their form labels stay English: the design covers the shop, not the admin.

## Development

```bash
python manage.py test                    # 43 tests in apps/toymodule/tests.py
python manage.py makemigrations          # after changing models.py
python manage.py migrate

# Production checks — these exercise the DEBUG=False branch of settings.py,
# which local development never reaches. CI runs both on every push.
DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=example.com \
  python manage.py check --deploy --fail-level WARNING
python manage.py collectstatic --no-input

python manage.py seed_catalog --reset    # replace the demo toys
```

`TEST_RUNNER` is a small subclass in `toystorewebsite/test_runner.py`. It names
the local apps explicitly, because `apps` is a namespace package and unittest
stopped discovering those in Python 3.11 — a bare `manage.py test` would
otherwise find zero tests and pass. It also swaps WhiteNoise's manifest static
storage for the plain one during tests, since tests run before `collectstatic`
has built a manifest.

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
