from django.contrib.auth.backends import ModelBackend, RemoteUserBackend
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
                        if str(value).lower() == str(claim_val).lower():
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
                    if str(value).lower() != str(claim_val).lower():
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


class staffOAuth2JWTBackend(ModelBackend):
    """Authentication backend for generic OAuth2 + JWT tokens."""

    @property
    def UserModel(self):
        from django.contrib.auth import get_user_model
        return get_user_model()

    @property
    def create_unknown_user(self):
        return getattr(settings, 'JWT_OAUTH2_CREATE_UNKNOWN_USER', True)

    def verify_token(self, token):
        import jwt
        try:
            verify_signature = getattr(settings, 'JWT_OAUTH2_VERIFY_SIGNATURE', False)
            if verify_signature:
                from jwt import PyJWKClient
                jwks_endpoint = getattr(settings, 'JWT_OAUTH2_JWKS_ENDPOINT', None)
                algorithms = getattr(settings, 'JWT_OAUTH2_SIGN_ALGOS', [getattr(settings, 'JWT_OAUTH2_SIGN_ALGO', 'RS256')])
                audience = getattr(settings, 'JWT_OAUTH2_CLIENT_ID', None)

                if jwks_endpoint and 'RS256' in algorithms:
                    jwk_client = PyJWKClient(jwks_endpoint)
                    signing_key = jwk_client.get_signing_key_from_jwt(token)
                    key = signing_key.key
                else:
                    key = getattr(settings, 'JWT_OAUTH2_SECRET_KEY', getattr(settings, 'JWT_OAUTH2_CLIENT_SECRET', None))

                if not key:
                    raise ValueError("No signature verification key or JWKS endpoint configured.")

                payload = jwt.decode(
                    token,
                    key,
                    algorithms=algorithms,
                    audience=audience,
                    options={"verify_aud": bool(audience)}
                )
            else:
                # Decode user info without verification
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False}
                )
            return payload
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to decode/verify JWT token: {e}")
            return None

    def verify_claims(self, claims):
        req_attrs = getattr(settings, 'JWT_OAUTH2_REQUIRED_ACCESS_ATTRIBUTES', [])
        for attribute, value in req_attrs:
            claim_val = claims.get(attribute)
            if claim_val is None:
                return False
            if isinstance(claim_val, list):
                if value not in claim_val:
                    return False
            else:
                if str(value).lower() != str(claim_val).lower():
                    return False
        return True

    def clean_username(self, username):
        if username and '@' in username:
            username = username.split('@')[0]
        return username

    def configure_user(self, request, user, created=True):
        """Configure user based on the decoded claims stored in request or backend."""
        claims = getattr(request, '_oauth2_jwt_claims', getattr(self, '_temp_claims', None))
        if not claims:
            return user

        # Set first_name
        first_name_claims = getattr(settings, 'JWT_OAUTH2_FIRST_NAME_CLAIMS', ['given_name', 'first_name', 'name'])
        for claim in first_name_claims:
            val = claims.get(claim)
            if val:
                user.first_name = val
                break

        # Set last_name
        last_name_claims = getattr(settings, 'JWT_OAUTH2_LAST_NAME_CLAIMS', ['family_name', 'last_name'])
        for claim in last_name_claims:
            val = claims.get(claim)
            if val:
                user.last_name = val
                break

        # Set email
        email_claim = getattr(settings, 'JWT_OAUTH2_EMAIL_CLAIM', 'email')
        user.email = claims.get(email_claim, '')

        # Set staff status
        user.is_staff = False
        staff_attrs = getattr(settings, 'JWT_OAUTH2_STAFF_ATTRIBUTES', [('administrator', True)])
        for attribute, value in staff_attrs:
            claim_val = claims.get(attribute)
            if claim_val is not None:
                if isinstance(claim_val, list):
                    if value in claim_val:
                        user.is_staff = True
                        break
                else:
                    if str(value).lower() == str(claim_val).lower():
                        user.is_staff = True
                        break

        # Set superuser status
        if claims.get('superuser') is True:
            user.is_superuser = True

        user.save()
        return user

    def authenticate(self, request, remote_user=None, token=None, **kwargs):
        """
        Authenticate with JWT token.
        """
        if token:
            claims = self.verify_token(token)
            if not claims:
                return None
            if not self.verify_claims(claims):
                return None

            username = None
            username_claims = getattr(settings, 'JWT_OAUTH2_USERNAME_CLAIMS', ['preferred_username', 'username', 'sub'])
            for claim in username_claims:
                username = claims.get(claim)
                if username:
                    break

            if not username:
                return None

            # Store claims temporarily where configure_user can access them
            self._temp_claims = claims
            if request:
                request._oauth2_jwt_claims = claims

            # Find or create user
            username = self.clean_username(username)
            if self.create_unknown_user:
                user, created = self.UserModel._default_manager.get_or_create(**{
                    self.UserModel.USERNAME_FIELD: username
                })
                user = self.configure_user(request, user, created=created)
            else:
                try:
                    user = self.UserModel._default_manager.get_by_natural_key(username)
                    user = self.configure_user(request, user, created=False)
                except self.UserModel.DoesNotExist:
                    user = None

            self._temp_claims = None
            if request and hasattr(request, '_oauth2_jwt_claims'):
                delattr(request, '_oauth2_jwt_claims')

            if user and self.user_can_authenticate(user):
                return user

        return None
