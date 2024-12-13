# Generated by Django 5.0.7 on 2024-10-16 18:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('jobstats', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL('ALTER TABLE jobstats_jobscript CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'),
        migrations.RunSQL('ALTER TABLE jobstats_jobscript MODIFY submit_script LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'),
    ]