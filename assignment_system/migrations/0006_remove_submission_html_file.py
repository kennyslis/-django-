# Generated by Django 4.2.16 on 2025-01-01 13:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('assignment_system', '0005_alter_submission_file_alter_submission_html_file'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='submission',
            name='html_file',
        ),
    ]
