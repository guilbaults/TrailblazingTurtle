from django.db import models


class JobScript(models.Model):
    id_job = models.PositiveIntegerField(primary_key=True)
    last_modified = models.DateTimeField(auto_now=True)
    submit_script = models.TextField()
