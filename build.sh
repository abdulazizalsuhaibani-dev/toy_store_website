#!/usr/bin/env bash
# Render build command. Runs on every deploy, before the new instance starts.
#
# migrate runs here rather than in a Render pre-deploy command because
# pre-deploy is a paid-plan feature. The build container reaches Supabase over
# the public internet exactly as the running service does, so it works from
# here; the trade-off is that migrations apply while the old instance is still
# serving, which is fine for this app's additive migrations.
set -o errexit
set -o nounset
set -o pipefail

pip install -r requirements.txt

# Collected into STATIC_ROOT and served by WhiteNoise. The build filesystem is
# carried into the running instance, so this survives even without a disk.
python manage.py collectstatic --no-input

python manage.py migrate

# Free Render instances have no shell, so createsuperuser cannot be run
# interactively after a deploy. When DJANGO_SUPERUSER_USERNAME and
# DJANGO_SUPERUSER_PASSWORD are set, create that account on the first build and
# skip it on every later one. Clear both from the Render dashboard once the
# account exists, so the password stops living in the environment.
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ['DJANGO_SUPERUSER_USERNAME']

if User.objects.filter(username=username).exists():
    print(f'Superuser {username!r} already exists; skipping creation.')
else:
    User.objects.create_superuser(
        username=username,
        email=os.environ.get('DJANGO_SUPERUSER_EMAIL', ''),
        password=os.environ['DJANGO_SUPERUSER_PASSWORD'],
    )
    print(f'Created superuser {username!r}.')
"
fi
