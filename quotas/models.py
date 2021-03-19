from django.db import models
import ldapdb.models
from ldapdb.models import fields
from django.conf import settings
from django.utils.encoding import smart_str

class LdapAllocation(ldapdb.models.Model):
    base_dn = 'dc=computecanada,dc=local'
    object_classes = ['ccAllocation']

    name = fields.CharField(db_column='cn', primary_key=True)
    gid = fields.IntegerField(db_column='gidNumber', unique=True)
    description = fields.CharField(db_column='description')
    members = fields.ListField(db_column='memberUid')
    resources = fields.ListField(db_column='ccResource')
    status = fields.CharField(db_column='ccRapStatus')
    rapi = fields.CharField(db_column='ccRapi')
    rap_type = fields.CharField(db_column='ccRapType')
    responsible = fields.CharField(db_column='ccResponsible')

    def parse_active_resources(self):
        resources = []
        for res in self.resources:
            if 'expired' in res or 'startdate' in res:
                continue
            s = res.split(':')
            name = s[0]
            resource_name = s[1]
            if settings.STORAGE_NAME in resource_name:
                quota_info = {}
                for quota in s[2:]:
                    key, value = quota.split('=')
                    quota_info[key] = float(value)
                resources.append(quota_info)
        return resources

class AcctStat(models.Model):
    class FileType(models.TextChoices):
        SYMLINK = 'symlink'
        DIR = 'dir'
        FILE = 'file'
        CHR = 'chr'
        BLK = 'blk'
        FIFO = 'fifo'
        SOCK = 'sock'

    class LhsmStatus(models.TextChoices):
        NONE = ''
        NEW = 'new'
        MODIFIED = 'modified'
        RETRIEVING = 'retrieving'
        ARCHIVING = 'archiving'
        SYNCHRO = 'synchro'
        RELEASED = 'released'

    uid = models.CharField(primary_key=True, max_length=127)
    gid = models.CharField(max_length=127)
    type = models.CharField(
        max_length=7,
        choices = FileType.choices,
    )
    lhsm_status = models.CharField(
        max_length=10,
        choices=LhsmStatus.choices,
    )
    size = models.PositiveBigIntegerField(blank=True, null=True)
    blocks = models.PositiveBigIntegerField(blank=True, null=True)
    count = models.PositiveBigIntegerField(blank=True, null=True)
    sz0 = models.PositiveBigIntegerField(blank=True, null=True)
    sz1 = models.PositiveBigIntegerField(blank=True, null=True)
    sz32 = models.PositiveBigIntegerField(blank=True, null=True)
    sz1k = models.PositiveBigIntegerField(db_column='sz1K', blank=True, null=True)  # Field name made lowercase.
    sz32k = models.PositiveBigIntegerField(db_column='sz32K', blank=True, null=True)  # Field name made lowercase.
    sz1m = models.PositiveBigIntegerField(db_column='sz1M', blank=True, null=True)  # Field name made lowercase.
    sz32m = models.PositiveBigIntegerField(db_column='sz32M', blank=True, null=True)  # Field name made lowercase.
    sz1g = models.PositiveBigIntegerField(db_column='sz1G', blank=True, null=True)  # Field name made lowercase.
    sz32g = models.PositiveBigIntegerField(db_column='sz32G', blank=True, null=True)  # Field name made lowercase.
    sz1t = models.PositiveBigIntegerField(db_column='sz1T', blank=True, null=True)  # Field name made lowercase.

    def uid_string(self):
        return smart_str(self.uid)

    class Meta:
        managed = False
        db_table = 'ACCT_STAT'
        unique_together = (('uid', 'gid', 'type', 'lhsm_status'),)
