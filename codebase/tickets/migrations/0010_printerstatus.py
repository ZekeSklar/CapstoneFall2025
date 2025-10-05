from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0009_issuesummaryrecipient'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrinterStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status_code', models.PositiveSmallIntegerField(default=0)),
                ('status_label', models.CharField(blank=True, max_length=50)),
                ('device_status_code', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('device_status_label', models.CharField(blank=True, max_length=50)),
                ('error_state_raw', models.CharField(blank=True, max_length=16)),
                ('error_flags', models.JSONField(blank=True, default=list)),
                ('alerts', models.JSONField(blank=True, default=list)),
                ('supplies', models.JSONField(blank=True, default=list)),
                ('attention', models.BooleanField(default=False)),
                ('snmp_ok', models.BooleanField(default=True)),
                ('snmp_message', models.CharField(blank=True, max_length=255)),
                ('fetched_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('printer', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='status', to='tickets.printer')),
            ],
            options={
                'verbose_name': 'Printer status',
                'verbose_name_plural': 'Printer statuses',
            },
        ),
    ]
