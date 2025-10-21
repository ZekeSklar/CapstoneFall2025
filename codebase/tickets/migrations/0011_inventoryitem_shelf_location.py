from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0010_printerstatus'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='shelf_row',
            field=models.CharField(blank=True, db_index=True, help_text='Shelf row letters (e.g., A, B, AA).', max_length=3, null=True),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='shelf_column',
            field=models.PositiveSmallIntegerField(blank=True, db_index=True, help_text='Shelf column number (e.g., 1, 2, 10).', null=True),
        ),
    ]

