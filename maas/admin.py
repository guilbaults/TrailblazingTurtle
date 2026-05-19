from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from maas.models import MAASProvider, MAASApiKey, MAASUsageRecord, sha256_key


class MAASProviderAdminForm(forms.ModelForm):
    clear_text_key = forms.CharField(
        label=_('API key (clear text)'),
        required=False,
        widget=forms.PasswordInput(
            attrs={
                'autocomplete': 'new-password',
                'placeholder': _('Enter a key or click Generate'),
            }
        ),
        help_text=_('Enter a clear-text key, or click Generate. It will be hashed (SHA-256) and stored. Leave blank when editing to keep the existing key.'),
    )

    class Meta:
        model = MAASProvider
        fields = '__all__'
        exclude = ('key',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(['name', 'url', 'clear_text_key', 'is_active', 'created_at', 'updated_at'])

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_key = self.cleaned_data.get('clear_text_key', '').strip()
        if raw_key:
            instance.key = sha256_key(raw_key)
        if commit:
            instance.save()
        return instance


class MAASApiKeyAdminForm(forms.ModelForm):
    clear_text_key = forms.CharField(
        label=_('API key (clear text)'),
        required=False,
        widget=forms.PasswordInput(
            attrs={
                'autocomplete': 'new-password',
                'placeholder': _('Enter a key or click Generate'),
            }
        ),
        help_text=_('Enter a clear-text key, or click Generate. It will be hashed (SHA-256) and stored. Leave blank when editing to keep the existing key.'),
    )

    class Meta:
        model = MAASApiKey
        fields = '__all__'
        exclude = ('key',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(['user', 'name', 'clear_text_key', 'created_at', 'expires_at', 'is_active', 'last_used_at'])

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_key = self.cleaned_data.get('clear_text_key', '').strip()
        if raw_key:
            instance.key = sha256_key(raw_key)
        if commit:
            instance.save()
        return instance


@admin.register(MAASProvider)
class MAASProviderAdmin(admin.ModelAdmin):
    form = MAASProviderAdminForm
    list_display = ('name', 'url', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'key')

    change_form_template = 'admin/maas/change_form.html'


@admin.register(MAASApiKey)
class MAASApiKeyAdmin(admin.ModelAdmin):
    form = MAASApiKeyAdminForm
    list_display = ('user', 'name', 'is_active', 'is_expired', 'created_at', 'expires_at', 'last_used_at')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'name')
    readonly_fields = ('created_at', 'last_used_at', 'key')

    change_form_template = 'admin/maas/change_form.html'


@admin.register(MAASUsageRecord)
class MAASUsageRecordAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'api_key', 'provider', 'model', 'input_tokens', 'output_tokens', 'cost', 'latency_ms', 'created_at')
    list_filter = ('provider', 'model')
    search_fields = ('request_id', 'model')
    readonly_fields = ('created_at',)
