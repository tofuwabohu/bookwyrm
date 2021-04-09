# Generated by Django 3.1.6 on 2021-03-21 01:01

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0054_auto_20210319_1942"),
    ]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="progress",
            field=models.IntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="comment",
            name="progress_mode",
            field=models.CharField(
                blank=True,
                choices=[("PG", "page"), ("PCT", "percent")],
                default="PG",
                max_length=3,
                null=True,
            ),
        ),
    ]
