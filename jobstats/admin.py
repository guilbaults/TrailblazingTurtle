from django.contrib import admin
from jobstats.models import JobScript, Sharing


class JobScriptAdmin(admin.ModelAdmin):
    pass


class SharingAdmin(admin.ModelAdmin):
    pass


admin.site.register(JobScript, JobScriptAdmin)
admin.site.register(Sharing, SharingAdmin)
