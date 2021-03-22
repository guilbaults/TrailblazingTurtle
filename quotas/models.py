from django.db import models
from django.conf import settings
from django.utils.encoding import smart_str


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
