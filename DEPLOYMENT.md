# Deploying to Render + Supabase

The deployed setup is a free Render web service running gunicorn, with both
stateful pieces on Supabase:

```
Browser ──► Render web service (gunicorn + WhiteNoise)
              ├─ static/  → collected at build time, served by WhiteNoise
              ├─ database → Supabase Postgres (session pooler)
              └─ uploads  → Supabase Storage (S3-compatible bucket)
```

Nothing stateful lives on Render, because **free Render instances have no
persistent disk** — the filesystem resets on every deploy and every restart.

`settings.py` reads all of this from the environment and falls back to SQLite
plus local file storage when the variables are absent, so `runserver`, the test
suite, and CI keep working with no extra configuration.

---

## 1. Supabase

Create a project at [supabase.com](https://supabase.com). Pick the region
closest to the Render region you will use in step 2 — every page view makes
several round trips to Postgres, so a mismatch here is the largest avoidable
latency cost in this setup. Save the database password it generates.

### 1a. Connection string

In the dashboard: **Connect** → **Session pooler**. Copy that URI. It looks
like:

```
postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Two ways to get this wrong, both of which fail only once deployed:

| Do not use | Why |
|---|---|
| `db.<ref>.supabase.co:5432` (direct connection) | Resolves to **IPv6 only**. Render cannot reach it; you get connection timeouts. |
| `...pooler.supabase.com:**6543**` (transaction pooler) | For serverless callers. Disables prepared statements, which Django's ORM uses. |

The **session pooler on port 5432** is IPv4 on every tier and is the right
choice for a long-lived server like gunicorn.

### 1a-bis. Lock PostgREST out of the Django tables

**Do this on any new Supabase project, before or right after the first
`migrate`.** It is the single most dangerous default in this setup.

Supabase assumes the app talks to Postgres through PostgREST using the `anon`
and `authenticated` roles, and its default privileges therefore grant those
roles full `SELECT/INSERT/UPDATE/DELETE/TRUNCATE` on everything in the `public`
schema, reachable over `https://<ref>.supabase.co/rest/v1/`. Row Level Security
is what normally contains that, and Django creates its tables without any.

Django does not use PostgREST at all — it connects directly as `postgres`. So
the grants buy nothing and expose everything: with only the *publishable* key,
which is designed to be public, anyone can read `auth_user` (password hashes
and emails), read `django_session` (session keys, so admin sessions can be
hijacked), and truncate `toymodule_product`.

Run this once in the SQL editor. It cannot affect the application, which
authenticates as `postgres` and keeps ownership and every privilege:

```sql
revoke all privileges on all tables    in schema public from anon, authenticated;
revoke all privileges on all sequences in schema public from anon, authenticated;
revoke all privileges on all functions in schema public from anon, authenticated;
revoke usage on schema public from anon, authenticated;

-- Future migrations create tables as `postgres`; without this they inherit the
-- same permissive defaults and reopen the hole.
alter default privileges in schema public revoke all on tables    from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke all on functions from anon, authenticated;
```

Verify with a request that should now be refused:

```bash
curl -s "https://<ref>.supabase.co/rest/v1/auth_user?select=id&limit=1" \
     -H "apikey: <publishable key>"
# expect 401 and SQLSTATE 42501, "permission denied"
```

`get_advisors` / the dashboard's Security Advisor should report no
`rls_disabled_in_public` findings afterwards.

### 1b. Storage bucket

**Storage** → **New bucket** → name it `product-images` → mark it **Public**.

Public matters: `settings.py` generates unsigned URLs on the assumption that
anyone may fetch a product image. A private bucket would need
`querystring_auth` turned back on and `custom_domain` removed.

Then **Storage** → **S3 Connection**, and note:

- the **endpoint**, ending in `/storage/v1/s3`
- the **region**
- **New access key** → the access key ID and secret (shown once)

---

## 2. Render

Push this branch, then in the Render dashboard: **New** → **Blueprint** → pick
this repository. `render.yaml` defines the service; Render prompts for the
values marked `sync: false`:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the session pooler URI from 1a |
| `SUPABASE_S3_ENDPOINT` | e.g. `https://<ref>.storage.supabase.co/storage/v1/s3` |
| `SUPABASE_S3_REGION` | e.g. `eu-central-1` |
| `SUPABASE_S3_BUCKET` | `product-images` |
| `SUPABASE_S3_ACCESS_KEY_ID` | from 1b |
| `SUPABASE_S3_SECRET_ACCESS_KEY` | from 1b |

`DJANGO_SECRET_KEY` is generated by Render and persists across deploys.
`DJANGO_DEBUG` is pinned to `False`.

`region: frankfurt` in `render.yaml` is a default — change it to match your
Supabase region.

### First admin user

Free instances have no shell, so `createsuperuser` cannot be run after a
deploy. Before the first build, add three more environment variables in the
Render dashboard:

```
DJANGO_SUPERUSER_USERNAME=<you>
DJANGO_SUPERUSER_EMAIL=<you@example.com>
DJANGO_SUPERUSER_PASSWORD=<a strong password>
```

`build.sh` creates that account if it does not already exist, and skips
otherwise. **Delete all three variables from the dashboard once the account
exists** so the password stops living in the environment.

---

## 3. Move the existing catalogue over (optional)

The eight products in your local `db.sqlite3` do not travel by themselves, and
neither do the image files they reference.

Export the products locally — **products only**. The four demo accounts in the
local database are not worth carrying to a public site, and their password
hashes are already in this repo's git history:

```bash
python manage.py dumpdata toymodule.Product --indent 2 -o products.json
```

Load them into Supabase by pointing a local run at the production database:

```bash
DATABASE_URL='<session pooler URI>' python manage.py loaddata products.json
```

Then push the image files into the bucket, again from your machine:

```bash
SUPABASE_S3_ENDPOINT=... SUPABASE_S3_REGION=... SUPABASE_S3_BUCKET=product-images \
SUPABASE_S3_ACCESS_KEY_ID=... SUPABASE_S3_SECRET_ACCESS_KEY=... \
python manage.py upload_media
```

`upload_media` walks `MEDIA_ROOT`, skips anything already in the bucket, and is
safe to re-run. Use `--dry-run` first to see what it would do.

Delete `products.json` afterwards; it does not belong in this public repo.

**Do not upload `db.sqlite3` to anything.** Start the production database from
`migrate` and a fresh superuser.

---

## 4. Verify

Locally, before pushing:

```bash
# Exercises the DEBUG=False branch: HTTPS redirect, secure cookies, HSTS.
DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=example.com \
  python manage.py check --deploy --fail-level WARNING

# Proves the WhiteNoise manifest builds and no static reference is dangling.
python manage.py collectstatic --no-input
```

CI runs both on every push.

After deploying, check that:

1. The site loads over HTTPS and `http://` redirects to it exactly once.
2. Product images render — their `src` should point at
   `https://<ref>.storage.supabase.co/storage/v1/object/public/product-images/...`,
   not at `/media/...` and not at the `/storage/v1/s3/` API path.
3. `/admin` accepts the superuser created in step 2.
4. Adding a product through `/addProduct` puts a new object in the Supabase
   bucket and shows it on the category page.
5. `/healthz` returns `200 ok`. Render polls it after each deploy; it returns
   `503` when the database is unreachable, which is the fastest way to tell a
   bad `DATABASE_URL` from an application error.

---

## Known limits of the free tier

These are properties of the plan, not bugs:

- **Render sleeps after 15 minutes of inactivity.** The next request takes
  roughly a minute while the instance wakes.
- **Supabase pauses a free project after 7 days of low activity.** Restoring it
  is a click in the dashboard, but until you do, every page 500s on a database
  connection error. If this site is meant to stay reachable, this is the first
  thing worth paying for.
- Free Supabase gives no database backups. `dumpdata` occasionally, or upgrade.
- The free plan allows **two active projects per organization**, 500 MB of
  database per project, and 1 GB of file storage shared across the org.
  Paused projects do not count against the two.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Connection timeouts to the database | Using the direct `db.<ref>.supabase.co` host (IPv6). Switch to the session pooler. |
| `ImproperlyConfigured: DJANGO_SECRET_KEY is not set` | The variable is missing with `DEBUG` off. Expected, and deliberate. |
| Infinite redirect loop | `SECURE_PROXY_SSL_HEADER` lost or a proxy not sending `X-Forwarded-Proto`. |
| `DisallowedHost` | Custom domain missing from `DJANGO_ALLOWED_HOSTS`. |
| Images 400 or 403 from the bucket | Bucket is not public, or `SUPABASE_S3_CUSTOM_DOMAIN` points at the `/s3` API path rather than `/object/public/<bucket>`. |
| Uploads fail with a 400 | An ACL is being sent. `default_acl` must stay `None`; Supabase implements no ACLs. |
| Django tables readable at `https://<ref>.supabase.co/rest/v1/...` | The `anon` grants of step 1a-bis were never revoked, or a later migration recreated the schema and re-inherited them. |
| Static files 404 in production | Build did not run `collectstatic`, or `whitenoise.middleware.WhiteNoiseMiddleware` is not directly below `SecurityMiddleware`. |
