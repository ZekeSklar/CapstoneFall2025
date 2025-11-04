from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0012_inventoryitem_shelf_row_single_letter'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='barcode',
            field=models.CharField(
                max_length=64,
                blank=True,
                null=True,
                unique=True,
                db_index=True,
                help_text='Optional UPC/EAN/Code128 text used by the scanner page.',
            ),
        ),
    ]

