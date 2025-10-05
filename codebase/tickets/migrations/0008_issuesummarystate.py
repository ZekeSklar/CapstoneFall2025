from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0007_printergroup_managers'),
    ]

    operations = [
        migrations.CreateModel(
            name='IssueSummaryState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Issue summary state',
                'verbose_name_plural': 'Issue summary state',
            },
        ),
    ]
