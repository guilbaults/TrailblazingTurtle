from djangosaml2.backends import Saml2Backend
from django.contrib.auth.backends import RemoteUserBackend

from django.conf import settings


class staffSaml2Backend(Saml2Backend):
    """This will add/remove the is_staff attribute from the user as appropriate."""
    def _update_user(self, user, attributes: dict, attribute_mapping: dict, force_save: bool = False):
        # figure out if user is active (i.e. can login)
        user.is_active = True
        for attribute, value in settings.SAML_CONFIG['required_access_attributes']:
            if attribute not in attributes or value not in attributes[attribute]:
                user.is_active = False

        # figure out if user is staff
        user.is_staff = False
        for attribute, value in settings.SAML_CONFIG['staff_attributes']:
            if attribute in attributes and value in attributes[attribute]:
                user.is_staff = True
                break

        user.first_name = attributes['givenName'][0]
        user.last_name = attributes['sn'][0]
        force_save = True
        return super()._update_user(user, attributes, attribute_mapping, force_save)


class staffRemoteUserBackend(RemoteUserBackend):
    """This does not remove the is_staff flag from the user."""
    def clean_username(self, username):
        if '@' in username:
            username = username.split('@')[0]
        return username

    def configure_user(self, request, user, created=True):
        if 'staff@computecanada.ca' in request.META['affiliation'] \
                or 'staff@alliancecan.ca' in request.META['affiliation']:
            user.is_staff = True
            user.save()
        else:
            user.is_staff = False
            user.save()
        return user
