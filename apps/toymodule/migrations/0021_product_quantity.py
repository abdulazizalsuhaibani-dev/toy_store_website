"""Track how many of each toy there are, instead of a yes/no flag.

Existing rows get 10 (the new field's default) if they were in stock and 0 if
they were not, so nothing changes on the shelf until somebody sets real counts.
"""

from django.db import migrations, models


def zero_out_of_stock(apps, schema_editor):
    apps.get_model("toymodule", "Product").objects.filter(in_stock=False).update(quantity=0)


def restore_in_stock(apps, schema_editor):
    Product = apps.get_model("toymodule", "Product")
    Product.objects.filter(quantity=0).update(in_stock=False)
    Product.objects.filter(quantity__gt=0).update(in_stock=True)


class Migration(migrations.Migration):

    dependencies = [("toymodule", "0020_order_status")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="quantity",
            field=models.PositiveIntegerField(default=10, help_text="How many are in stock."),
        ),
        migrations.RunPython(zero_out_of_stock, restore_in_stock),
        migrations.RemoveField(model_name="product", name="in_stock"),
    ]
