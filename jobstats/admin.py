from django.contrib import admin
from jobstats.models import JobScript, SharingAgreement


class JobScriptAdmin(admin.ModelAdmin):
    pass


class SharingAgreementAdmin(admin.ModelAdmin):
    pass


admin.site.register(JobScript, JobScriptAdmin)
admin.site.register(SharingAgreement, SharingAgreementAdmin)
