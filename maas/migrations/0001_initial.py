# Generated migration for maas module

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MAASProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='name')),
                ('url', models.URLField(max_length=500, verbose_name='base URL')),
                ('key', models.CharField(max_length=255, verbose_name='API key (hashed)')),
                ('key_hash', models.CharField(db_index=True, max_length=64, verbose_name='key hash (lookup)')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated')),
            ],
            options={
                'verbose_name': 'MAAS provider',
                'verbose_name_plural': 'MAAS providers',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='MAASApiKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('key', models.CharField(max_length=255, verbose_name='API key (hashed)')),
                ('key_hash', models.CharField(db_index=True, max_length=64, verbose_name='key hash (lookup)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='expires')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('last_used_at', models.DateTimeField(blank=True, null=True, verbose_name='last used')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maas_keys', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'MAAS API key',
                'verbose_name_plural': 'MAAS API keys',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user'], name='maas_apikey_user_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='MAASUsageRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_id', models.CharField(max_length=255, unique=True, verbose_name='request ID')),
                ('model', models.CharField(max_length=255, verbose_name='model')),
                ('endpoint', models.CharField(max_length=500, verbose_name='endpoint')),
                ('input_tokens', models.PositiveIntegerField(verbose_name='input tokens')),
                ('output_tokens', models.PositiveIntegerField(verbose_name='output tokens')),
                ('cost', models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True, verbose_name='cost')),
                ('latency_ms', models.PositiveIntegerField(verbose_name='latency (ms)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('api_key', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usagerecords', to='maas.maasapikey', verbose_name='API key')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usagerecords', to='maas.maasprovider', verbose_name='provider')),
            ],
            options={
                'verbose_name': 'MAAS usage record',
                'verbose_name_plural': 'MAAS usage records',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['api_key', '-created_at'], name='maas_usage_apikey_created_idx'),
                    models.Index(fields=['provider'], name='maas_usage_provider_idx'),
                    models.Index(fields=['model'], name='maas_usage_model_idx'),
                ],
            },
        ),
    ]
