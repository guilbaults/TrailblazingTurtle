# Generated by Django 3.1.7 on 2021-05-27 19:57

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='JobScript',
            fields=[
                ('id_job', models.PositiveIntegerField(primary_key=True, serialize=False)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('submit_script', models.TextField()),
            ],
        ),
    ]
