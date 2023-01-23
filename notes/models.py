from django.db import models
from django.core.exceptions import ValidationError
from userportal.common import username_to_uid
from slurm.models import JobTable, AssocTable
from django.contrib.auth.models import User


def validate_valid_username(username):
    if username is None or username == '':
        # we allow empty usernames in the note
        return
    try:
        username_to_uid(username)
    except:  # noqa
        raise ValidationError('Invalid username')


def validate_job_id(job_id):
    if job_id is None or job_id == '':
        # we allow empty job_id in the note
        return
    try:
        JobTable.objects.get(id_job=job_id)
        return
    except JobTable.DoesNotExist:
        raise ValidationError('Invalid job_id')


def validate_account(account):
    if account is None or account == '':
        # we allow empty account in the note
        return
    exist = AssocTable.objects.filter(acct=account).exists()
    if not exist:
        raise ValidationError('Invalid account')
    return


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
        return "/secure/notes/%i/" % self.id
