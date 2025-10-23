from django.db import migrations, models
import django.core.validators


def normalize_shelf_row(apps, schema_editor):
    InventoryItem = apps.get_model('tickets', 'InventoryItem')
    for item in InventoryItem.objects.all().only('id', 'shelf_row'):
        val = item.shelf_row or ''
        val = ''.join(ch for ch in val.strip().upper() if ch.isalpha())[:1]
        item.shelf_row = val or None
        item.save(update_fields=['shelf_row'])


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0011_inventoryitem_shelf_location'),
    ]

    operations = [
        migrations.RunPython(normalize_shelf_row, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='inventoryitem',
            name='shelf_row',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Shelf row letter (A-Z).',
                max_length=1,
                null=True,
                validators=[django.core.validators.RegexValidator('^[A-Za-z]$', message='Shelf row must be a single letter (A-Z).')],
            ),
        ),
    ]

