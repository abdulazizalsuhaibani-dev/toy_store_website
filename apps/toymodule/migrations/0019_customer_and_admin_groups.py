"""Create the Customer and Admin groups, so a fresh `migrate` produces them.

Permissions are normally created by a post-migrate signal, which has not run
yet when a data migration executes on a new database, so they are created
here first. Names are repeated from `roles.py` on purpose: a migration should
keep meaning what it meant when it was written.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

# codename prefixes per model the Admin role may use.
ADMIN_PERMISSIONS = {
    "product": ("add", "change", "delete", "view"),
    "category": ("add", "change", "delete", "view"),
    "order": ("change", "view"),
}


def create_groups(apps, schema_editor):
    app_config = apps.get_app_config("toymodule")
    # The historical app config has no models_module, which create_permissions
    # skips apps without; any truthy value gets past that check.
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    Group.objects.get_or_create(name="Customer")
    admin, _ = Group.objects.get_or_create(name="Admin")
    codenames = [f"{action}_{model}" for model, actions in ADMIN_PERMISSIONS.items() for action in actions]
    admin.permissions.set(Permission.objects.filter(content_type__app_label="toymodule", codename__in=codenames))


def remove_groups(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=["Customer", "Admin"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("toymodule", "0018_drop_pcategory"),
    ]

    operations = [migrations.RunPython(create_groups, remove_groups)]
