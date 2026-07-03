from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings

try:
    from djangosaml2.backends import Saml2Backend

    class staffSaml2Backend(Saml2Backend):
        """This will add/remove the is_staff attribute from the user as appropriate."""
        def _update_user(self, user, attributes: dict, attribute_mapping: dict, force_save: bool = False):
            # figure out if user is active (i.e. can login)
            user.is_active = True
            for attribute, value in settings.SAML_CONFIG['required_access_attributes']:
                if attribute not in attributes or value not in attributes[attribute]:
                    user.is_active = False
                    break

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


except ImportError:
    pass


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


try:
    from django_auth_ldap.backend import LDAPBackend

    class staffLdapBackend(LDAPBackend):
        def get_or_build_user(self, username, ldap_user):
            user, built = super().get_or_build_user(username, ldap_user)

            # figure out if user is active (i.e. can login)
            user.is_active = True
            for attribute, value in settings.LDAP_CONFIG['required_access_attributes']:
                if attribute not in ldap_user.attrs.data or value not in ldap_user.attrs.data[attribute]:
                    user.is_active = False
                    break

            user.is_staff = False
            for attribute, value in settings.LDAP_CONFIG['staff_attributes']:
                if attribute in ldap_user.attrs.data and value in ldap_user.attrs.data[attribute]:
                    user.is_staff = True

            return user, built


except ImportError:
    pass

try:
    from mozilla_django_oidc.auth import OIDCAuthenticationBackend
    from django.conf import settings

    class staffOIDCBackend(OIDCAuthenticationBackend):
        """Claims verifications is done in _update_user_attributes"""
        def verify_claims(self, claims):
            return True

        """Get users that match by username"""
        def filter_users_by_claims(self, claims):
            username = self.get_username(claims)
            return self.UserModel.objects.filter(username__iexact=username)

        """This will add/remove the is_staff and is_active attributes from the user as appropriate based on OIDC claims."""
        def get_username(self, claims):
            username = claims.get('preferred_username')
            if not username:
                username = claims.get('sub')

            if username and '@' in username:
                username = username.split('@')[0]
            return username

        def _update_user_attributes(self, user, claims):
            user.is_staff = False
            staff_attrs = getattr(settings, 'OIDC_STAFF_ATTRIBUTES', [('groups', 'staff')])
            for attribute, value in staff_attrs:
                claim_val = claims.get(attribute)
                if claim_val:
                    if isinstance(claim_val, list):
                        if value in claim_val:
                            user.is_staff = True
                            break
                    else:
                        if value == claim_val:
                            user.is_staff = True
                            break

            user.is_active = True
            req_attrs = getattr(settings, 'OIDC_REQUIRED_ACCESS_ATTRIBUTES', [])
            for attribute, value in req_attrs:
                claim_val = claims.get(attribute)
                if not claim_val:
                    user.is_active = False
                    break
                if isinstance(claim_val, list):
                    if value not in claim_val:
                        user.is_active = False
                        break
                else:
                    if value != claim_val:
                        user.is_active = False
                        break

            user.first_name = claims.get('given_name', claims.get('first_name', ''))
            user.last_name = claims.get('family_name', claims.get('last_name', ''))
            user.save()
            return user

        def create_user(self, claims):
            user = super().create_user(claims)
            return self._update_user_attributes(user, claims)

        def update_user(self, user, claims):
            user = super().update_user(user, claims)
            return self._update_user_attributes(user, claims)
except ImportError:
    pass
