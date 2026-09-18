"""Tighten what 0017 made safe to tighten.

`slug` can only be unique once every row has one, and `pcategory` can only go
once every product points at a `Category` instead.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("toymodule", "0017_seed_storefront_data")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="slug",
            field=models.SlugField(blank=True, max_length=120, unique=True),
        ),
        migrations.RemoveField(model_name="product", name="pcategory"),
    ]
