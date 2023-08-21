import ldapdb.models
from ldapdb.models import fields
from django.conf import settings


class LdapUser(ldapdb.models.Model):
    """
    Class for representing an LDAP user entry.
    """
    # LDAP meta-data
    base_dn = settings.LDAP_BASE_DN
    object_classes = ['PosixAccount']

    # posixAccount
    username = fields.CharField(db_column='uid', primary_key=True)
    uid = fields.IntegerField(db_column='uidNumber', unique=True)
    full_name = fields.CharField(db_column='cn')
    group = fields.IntegerField(db_column='gidNumber')
    home_directory = fields.CharField(db_column='homeDirectory')
    login_shell = fields.CharField(db_column='loginShell', default='/bin/bash')

    def __str__(self):
        return self.username

    def __unicode__(self):
        return self.full_name


class LdapCCAccount(ldapdb.models.Model):
    """
    Class for representing an LDAP user entry in ccAccount.
    Pseudo users does not have a ccAccount, only a posixAccount.
    """
    # LDAP meta-data
    base_dn = settings.LDAP_BASE_DN
    object_classes = ['ccAccount']

    # posixAccount
    username = fields.CharField(db_column='uid', primary_key=True)
    uid = fields.IntegerField(db_column='uidNumber', unique=True)
    full_name = fields.CharField(db_column='cn')
    group = fields.IntegerField(db_column='gidNumber')
    preferredLanguage = fields.CharField(db_column='preferredLanguage')
    ccCertSubject = fields.CharField(db_column='ccCertSubject')
    ccServiceAccess = fields.CharField(db_column='ccServiceAccess')
    SSHPUBLICKEY = fields.CharField(db_column='SSHPUBLICKEY')
    employeeType = fields.CharField(db_column='employeeType')
    home_directory = fields.CharField(db_column='homeDirectory')
    login_shell = fields.CharField(db_column='loginShell', default='/bin/bash')

    def __str__(self):
        return self.username

    def __unicode__(self):
        return self.full_name


class LdapAllocation(ldapdb.models.Model):
    base_dn = settings.LDAP_BASE_DN
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
            resource_name = s[1]
            if resource_name == settings.STORAGE_NAME:
                quota_info = {}
                for quota in s[2:]:
                    key, value = quota.split('=')
                    quota_info[key] = float(value)
                resources.append(quota_info)
            if resource_name == settings.COMPUTE_NAME + '-compute' or resource_name == settings.COMPUTE_NAME + '-gpu':
                compute_info = {}
                for compute in s[2:]:
                    key, value = compute.split('=')
                    compute_info[key] = float(value)
                resources.append(compute_info)
        return resources
