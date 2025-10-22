from django.conf import settings
from django.db import migrations, models



class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0008_issuesummarystate'),
    ]

    operations = [
        migrations.CreateModel(
            name='IssueSummaryRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subscribed', models.BooleanField(default=True, help_text='Receive the daily printer issue summary email.', verbose_name='Receive daily issue summary')),
                ('user', models.OneToOneField(on_delete=models.CASCADE, related_name='issue_summary_recipient', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Issue summary recipient',
                'verbose_name_plural': 'Issue summary recipients',
            },
        ),
    ]
