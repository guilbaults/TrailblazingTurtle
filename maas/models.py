import hashlib
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


def sha256_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


class MAASProvider(models.Model):
    name = models.CharField(_('name'), max_length=255, unique=True)
    url = models.URLField(_('base URL'), max_length=500)
    key = models.CharField(_('API key (hashed)'), max_length=255)
    key_hash = models.CharField(_('key hash (lookup)'), max_length=64, db_index=True)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated'), auto_now=True)

    class Meta:
        verbose_name = _('MAAS provider')
        verbose_name_plural = _('MAAS providers')
        ordering = ['name']

    def __str__(self):
        return self.name


class MAASApiKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='maas_keys', verbose_name=_('user'))
    name = models.CharField(_('name'), max_length=255)
    key = models.CharField(_('API key (hashed)'), max_length=255)
    key_hash = models.CharField(_('key hash (lookup)'), max_length=64, db_index=True)
    created_at = models.DateTimeField(_('created'), auto_now_add=True)
    expires_at = models.DateTimeField(_('expires'), null=True, blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    last_used_at = models.DateTimeField(_('last used'), null=True, blank=True)

    class Meta:
        verbose_name = _('MAAS API key')
        verbose_name_plural = _('MAAS API keys')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.name}'

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        from django.utils import timezone
        return timezone.now() >= self.expires_at


class MAASUsageRecord(models.Model):
    api_key = models.ForeignKey(MAASApiKey, on_delete=models.CASCADE, related_name='usagerecords', verbose_name=_('API key'))
    provider = models.ForeignKey(MAASProvider, on_delete=models.CASCADE, related_name='usagerecords', verbose_name=_('provider'))
    request_id = models.CharField(_('request ID'), max_length=255, unique=True)
    model = models.CharField(_('model'), max_length=255)
    endpoint = models.CharField(_('endpoint'), max_length=500)
    input_tokens = models.PositiveIntegerField(_('input tokens'))
    output_tokens = models.PositiveIntegerField(_('output tokens'))
    cost = models.DecimalField(_('cost'), max_digits=10, decimal_places=6, null=True, blank=True)
    latency_ms = models.PositiveIntegerField(_('latency (ms)'))
    created_at = models.DateTimeField(_('created'), auto_now_add=True)

    class Meta:
        verbose_name = _('MAAS usage record')
        verbose_name_plural = _('MAAS usage records')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key', '-created_at']),
            models.Index(fields=['provider']),
            models.Index(fields=['model']),
        ]

    def __str__(self):
        return f'{self.request_id} - {self.model}'
