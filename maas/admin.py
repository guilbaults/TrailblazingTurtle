from django.contrib import admin
from maas.models import MAASProvider, MAASApiKey, MAASUsageRecord


@admin.register(MAASProvider)
class MAASProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'key_hash')


@admin.register(MAASApiKey)
class MAASApiKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'is_active', 'is_expired', 'created_at', 'expires_at', 'last_used_at')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'name')
    readonly_fields = ('created_at', 'last_used_at', 'key_hash')


@admin.register(MAASUsageRecord)
class MAASUsageRecordAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'api_key', 'provider', 'model', 'input_tokens', 'output_tokens', 'cost', 'latency_ms', 'created_at')
    list_filter = ('provider', 'model')
    search_fields = ('request_id', 'model')
    readonly_fields = ('created_at',)
