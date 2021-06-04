from django.contrib import admin
from jobstats.models import JobScript


class JobScriptAdmin(admin.ModelAdmin):
    pass


admin.site.register(JobScript, JobScriptAdmin)
