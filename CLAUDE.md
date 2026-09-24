# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Django 5.0 toy store website. Single Django app (`apps/toymodule`) providing a bilingual (EN/AR, with RTL) product catalog browsable by category, search with filters, a product detail page, a cart and checkout, user registration/login, and a dashboard for adding products.

The storefront implements the **Happybox** design from Claude Design project `56e1a170` ("Wobblebox Toy Store"). That project's `github.md` maps each design screen back to the files here. The design's copy, palette, category list and currency table were ported into `strings.py`, `static/css/happybox.css` and migration `0017`.

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

# Run tests (CI invokes this). A custom TEST_RUNNER is required - see Notes.
python manage.py test

# Load the eight demo toys from the design. Opt-in, matches on slug, never
# duplicates. Categories/currencies/delivery options come from migrate instead.
python manage.py seed_catalog
python manage.py seed_catalog --reset

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
  - `models.py` — `Category`, `Currency`, `DeliveryOption`, `Product`, `Cart`/`CartItem`, `Order`/`OrderItem`. `Product` keeps `pname`/`pimage`/`pprice` under their original names (fifteen migrations and every template call them that); `pprice` is now a `DecimalField`, and `pcategory` is gone, replaced by a `category` FK. Categories are rows, so adding a shelf no longer means editing a view.
  - `strings.py` — every UI string as an `(English, Arabic)` pair, flattened per request into `{{ t.someKey }}`. A dict rather than gettext because the site is two languages chosen by a header toggle, not by `Accept-Language`.
  - `storefront.py` — per-request language, currency and cart, all session-backed. `adopt_cart()` must be called with a cart looked up **before** `login()`, because Django cycles the session key on login.
  - `context_processors.py` — `storefront_context` supplies `t`, `lang`, `text_dir`, `currency`, `nav_categories` and `cart_count` to every template. Registered in settings; the header needs all of it on every page.
  - `templatetags/happybox.py` — `{% money %}`, `{% money_in %}` (an order's recorded currency), `{% label %}`/`{% blurb %}` (language-aware model copy), and `{% querystring %}` (rebuild the query string with one filter replaced).
  - `views.py` — function-based views only (no CBVs, no DRF/API layer). `_catalogue()` is the shared filter/sort helper behind the listing and search screens. `dashboard`, `accountInfo`, `orders` and `addProduct` are gated with `@login_required(login_url='login')`.
  - `forms.py` — `AddProductForm` (explicit field list, not `__all__`), `AddUserForm`, `LoginForm`, `CheckoutForm`. Auth is Django's built-in `django.contrib.auth` — no custom User model.
  - `urls.py` — all app routes, plus 301s from the original `/baby-toys` style URLs, plus the `static()` helper appended to serve `MEDIA_URL` in development.
  - `admin.py` — registers every model. `OrderItem` is a read-only inline: a line is a snapshot of what was charged.
  - `tests.py` — 47 tests covering currency conversion, the filters, the cart, checkout totals, and who may read an order confirmation.
- **`apps/templates/`** — the single template root (`TEMPLATE_DIR` in `settings.py`, `APP_DIRS` also on). `layouts/base.html` is the shared layout; `includes/` holds `header.html`, `footer.html`, `logo.html`, `mascot.html`, `product_card.html`, `product_image.html` and `empty_shelf.html`; `toymodule/` holds the page templates. When adding a page, extend `layouts/base.html` and add a template under `apps/templates/toymodule/`.
- **Styling** is `static/css/happybox.css`, hand-written, no CSS framework. The look is four rules: 3px ink outlines on everything, generous radii, a hard offset shadow instead of a blur, and a press that moves the element down into its own shadow. Keep those and a new component will belong. RTL rides on logical properties (`inset-inline-start`, `margin-inline-start`), so `[dir="rtl"]` overrides are only needed where a shape is genuinely directional.
- Forms still go through `django-crispy-forms` + `crispy-bootstrap5` (`CRISPY_TEMPLATE_PACK = "bootstrap5"`) — render with `{{ form|crispy }}`. Bootstrap itself is **not** loaded; `happybox.css` styles the class names the pack emits (`.form-control`, `.form-label`, `.errorlist`, ...). Anything new the pack starts emitting needs a rule there.
- **Django template comments are single-line.** A `{# ... #}` spanning more than one line is not a comment — it renders as page text. Use `{% comment %}...{% endcomment %}` for anything multi-line.
- `apps` is a Django namespace package (no `apps/__init__.py`) — this is intentional for Django 5, not an oversight.
- **Deployment** — `render.yaml` (Render Blueprint), `build.sh` (install → `collectstatic` → `migrate` → optional first superuser), `.python-version`, and `DEPLOYMENT.md` (the runbook, including the Supabase gotchas). Target is a free Render web service with Postgres and uploaded images on Supabase; `apps/toymodule/management/commands/upload_media.py` does the one-time push of `media/` into the bucket. Free Render instances have no persistent disk, which is why neither the database nor uploads may live on them.

## Notes for changes

- `SECRET_KEY` is read from `DJANGO_SECRET_KEY` (loaded from a gitignored `.env`). If it's unset, startup raises `ImproperlyConfigured` when `DEBUG` is off, and under `DEBUG` falls back to a throwaway key generated per process with a `RuntimeWarning` — so a fresh clone still runs, but sessions reset on every restart until `.env` is filled in. CI supplies the key explicitly.
- `DEBUG` comes from `DJANGO_DEBUG` and **defaults to `False`**, so a deployed host that is missing the variable fails safe. Local development sets `DJANGO_DEBUG=True` in `.env` — a clone without one will start in production mode and refuse to run without a secret key. Everything under `if not DEBUG:` in `settings.py` (HTTPS redirect, secure cookies, HSTS) is off locally by design.
- Deployment settings are all env-driven with local fallbacks, so `runserver` and `manage.py test` need no configuration: no `DATABASE_URL` means SQLite, no `SUPABASE_S3_ENDPOINT` means local file storage. This is deliberate — one settings module, no `settings/prod.py` split, and CI exercises the same file production does.
- This repo is **public**, and `db.sqlite3` remains in git history (with four demo accounts' emails and pbkdf2 password hashes) even though it's no longer tracked. The original `SECRET_KEY` is likewise still in history and has been rotated, so the leaked one is worthless. Don't commit real credentials or user data here.
- Adding a product category is now a `Category` row (admin, or a data migration) — no code change. The old free-text `pcategory` and its never-wired-in `CATEGORIES_CHOICES` are gone.
- **Money** is stored once, in the base currency (`Currency.is_base`, seeded as SAR because that is what every template has printed next to `pprice` since the app was written). `Currency.rate` is units per USD, copied from the design, and `convert()` divides by the base rate — so the design's numbers transfer verbatim while existing prices keep their meaning. Render prices with `{% money %}`, never `{{ p.pprice }}`. An `Order` records `currency_code`; use `{% money_in %}` on receipts so a shopper who later switches currency still sees the total they agreed to.
- **Checkout takes no payment.** The card number/expiry/CVC inputs on `checkout.html` are `disabled`, unnamed and never posted, and `Order` has no card columns. This is a public demo repo — keep it that way.
- **`manage.py test` needs `TEST_RUNNER`** (`toystorewebsite/test_runner.py`). `apps` is a namespace package and unittest stopped discovering those in Python 3.11, so plain discovery finds zero tests *and exits 0* — a green CI that tested nothing. The runner also swaps WhiteNoise's manifest static storage for the plain one, because tests run with `DEBUG=False` and before `collectstatic`.
- **Never let an `<option>` inherit a web font.** Firefox on Windows draws the dropdown list as a native popup *outside* the page, where `@font-face` fonts are not loaded, so an option left to inherit Baloo 2 or Nunito renders as blank glyphs — a list of empty rows, while the closed control (drawn in-page) looks fine. `happybox.css` pins `select option` to a system stack for exactly this reason. Don't give it a `background` either: that paints a slab sized to the option rather than the popup.
- **`color-scheme` must be declared wherever CSS paints form colours.** The `<select>` dropdown list, scrollbars and spinners are drawn by the browser, not by a stylesheet, and they follow the OS unless the page says otherwise — so author-painted text lands on a popup of the opposite scheme and the rows read as blank. `happybox.css` declares `light` (the design has no dark variant). Django 5.0's admin swaps its colours under `@media (prefers-color-scheme: dark)` but sets no `color-scheme`, which has the same effect in reverse; `apps/templates/admin/base_site.html` exists only to add `static/css/admin_color_scheme.css`, which supplies it for all three of the admin's theme states. Drop both if a later Django fixes it upstream.
- Django 4.1+ always wraps the template loaders in `cached.Loader`, and `runserver`'s file watcher is what resets it. `runserver --noreload` therefore serves **stale templates** until restarted. Don't debug a template change against `--noreload`. A brand-new template that *shadows* one from a library (as `apps/templates/admin/base_site.html` shadows the admin's) needs a full restart even with the reloader on, because the loader has already cached where that name resolves to.
- `annotate()` discards `Meta.ordering` (aggregation builds its own `GROUP BY`). Restate `.order_by()` after any `annotate()` whose order matters — `index` does this for the category cards.
