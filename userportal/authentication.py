from djangosaml2.backends import Saml2Backend
from django.contrib.auth.backends import RemoteUserBackend


class staffSaml2Backend(Saml2Backend):
    """This will add/remove the is_staff attribute from the user as appropriate."""
    def _update_user(self, user, attributes: dict, attribute_mapping: dict, force_save: bool = False):
        if 'eduPersonAffiliation' in attributes:
            if 'staff' in attributes['eduPersonAffiliation']:
                user.is_staff = True
            else:
                user.is_staff = False
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
