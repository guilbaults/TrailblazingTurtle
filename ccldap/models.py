from django.db import models
import ldapdb.models
from ldapdb.models import fields
from django.conf import settings
from django.utils.encoding import smart_str

class LdapUser(ldapdb.models.Model):
    """
    Class for representing an LDAP user entry.
    """
    # LDAP meta-data
    base_dn = 'ou=People,dc=computecanada,dc=local'
    object_classes = ['ccAccount']

    # posixAccount
    username = fields.CharField(db_column='uid', primary_key=True)
    uid = fields.IntegerField(db_column='uidNumber', unique=True)
    full_name = fields.CharField(db_column='cn')
    group = fields.IntegerField(db_column='gidNumber')
    preferredLanguage = fields.CharField(db_column='preferredLanguage')
    ccCertSubject = fields.CharField(db_column='ccCertSubject')
    SSHPUBLICKEY = fields.CharField(db_column='SSHPUBLICKEY')
    employeeType = fields.CharField(db_column='employeeType')
    home_directory = fields.CharField(db_column='homeDirectory')
    login_shell = fields.CharField(db_column='loginShell', default='/bin/bash')

    def __str__(self):
        return self.username

    def __unicode__(self):
        return self.full_name

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
