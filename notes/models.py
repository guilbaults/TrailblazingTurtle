from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.conf import settings
from slurm.models import validate_job_id, validate_account, validate_valid_username


class Note(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    title = models.CharField(max_length=255)
    notes = models.TextField()
    # optional external ticket id
    ticket_id = models.CharField(max_length=255, null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # These can't be foreign keys because all the info are not in the portal or are from slurm
    # Fields are optional because the note can be about an overall account for example
    job_id = models.PositiveIntegerField(null=True, blank=True, validators=[validate_job_id])
    username = models.CharField(max_length=255, null=True, blank=True, validators=[validate_valid_username])
    account = models.CharField(max_length=255, null=True, blank=True, validators=[validate_account])

    class Meta:
        ordering = ['-modified_at']
        verbose_name = 'Note'
        verbose_name_plural = 'Notes'

    def __str__(self):
        return '{} - {}'.format(self.id, self.title)

    def clean(self):
        if self.username is None and self.job_id is None and self.account is None:
            raise ValidationError('At least one of username, job_id or account must be set')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_absolute_url(self):
        return "{}secure/notes/{}/".format(settings.BASE_URL, self.id)
