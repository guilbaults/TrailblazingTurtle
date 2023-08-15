from django.db import models
from django.core.exceptions import ValidationError
from slurm.models import validate_job_id, validate_account, validate_valid_username


class JobScript(models.Model):
    id_job = models.PositiveIntegerField(primary_key=True)
    last_modified = models.DateTimeField(auto_now=True)
    submit_script = models.TextField()


class Sharing(models.Model):
    # Users can share their jobstats with other users or accounts
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255, validators=[validate_valid_username])

    # These can't be foreign keys because all the info are not in the portal or are from slurm
    job_id = models.PositiveIntegerField(null=True, blank=True, validators=[validate_job_id])
    shared_with = models.CharField(max_length=255, null=True, blank=True, validators=[validate_valid_username])
    account = models.CharField(max_length=255, null=True, blank=True, validators=[validate_account])

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return '{} - {} {} {}'.format(self.id, self.job_id, self.shared_with, self.account)

    def clean(self):
        if self.shared_with == '':
            self.shared_with = None
        if self.job_id == '':
            self.job_id = None
        if self.account == '':
            self.account = None

        # The user want to share with a specific user or account
        if self.shared_with is None and self.job_id is None and self.account is None:
            raise ValidationError('At least one of shared_with, job_id, or account must be set')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
