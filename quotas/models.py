from django.db import models
import ldapdb.models
from ldapdb.models import fields
from django.conf import settings

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
