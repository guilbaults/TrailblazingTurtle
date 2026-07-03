from djangosaml2.backends import Saml2Backend
from django.contrib.auth.backends import ModelBackend, RemoteUserBackend


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


class staffOpenEdxBackend(ModelBackend):
    """Authentication backend for OpenEdX OAuth2 + JWT tokens, using ModelBackend."""

    @property
    def UserModel(self):
        from django.contrib.auth import get_user_model
        return get_user_model()

    @property
    def create_unknown_user(self):
        return getattr(settings, 'OPENEDX_CREATE_UNKNOWN_USER', True)

    def verify_token(self, token):
        import jwt
        try:
            verify_signature = getattr(settings, 'OPENEDX_VERIFY_SIGNATURE', False)
            if verify_signature:
                from jwt import PyJWKClient
                jwks_endpoint = getattr(settings, 'OPENEDX_JWKS_ENDPOINT', None)
                if not jwks_endpoint and hasattr(settings, 'OPENEDX_LMS_URL'):
                    jwks_endpoint = f"{settings.OPENEDX_LMS_URL.rstrip('/')}/oauth2/jwks/"

                algorithms = [getattr(settings, 'OPENEDX_SIGN_ALGO', 'RS256')]
                audience = getattr(settings, 'OPENEDX_CLIENT_ID', None)

                if jwks_endpoint and 'RS256' in algorithms:
                    jwk_client = PyJWKClient(jwks_endpoint)
                    signing_key = jwk_client.get_signing_key_from_jwt(token)
                    key = signing_key.key
                else:
                    key = getattr(settings, 'OPENEDX_SECRET_KEY', getattr(settings, 'OPENEDX_CLIENT_SECRET', None))

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
                # Decode user info without verification, inspired by openedx_sso_security_manager in tutor-contrib-aspects
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False}
                )
            return payload
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to decode/verify OpenEdX JWT token: {e}")
            return None

    def verify_claims(self, claims):
        req_attrs = getattr(settings, 'OPENEDX_REQUIRED_ACCESS_ATTRIBUTES', [])
        for attribute, value in req_attrs:
            claim_val = claims.get(attribute)
            if claim_val is None:
                return False
            if isinstance(claim_val, list):
                if value not in claim_val:
                    return False
            else:
                if value != claim_val:
                    return False
        return True

    def clean_username(self, username):
        if username and '@' in username:
            username = username.split('@')[0]
        return username

    def configure_user(self, request, user, created=True):
        """Configure user based on the decoded claims stored in request or backend."""
        claims = getattr(request, '_openedx_claims', getattr(self, '_temp_claims', None))
        if not claims:
            return user

        user.first_name = claims.get('given_name', claims.get('first_name', claims.get('name', '')))
        user.last_name = claims.get('family_name', claims.get('last_name', ''))
        user.email = claims.get('email', '')

        # Set staff status
        user.is_staff = False
        staff_attrs = getattr(settings, 'OPENEDX_STAFF_ATTRIBUTES', [('administrator', True)])
        for attribute, value in staff_attrs:
            claim_val = claims.get(attribute)
            if claim_val is not None:
                if isinstance(claim_val, list):
                    if value in claim_val:
                        user.is_staff = True
                        break
                else:
                    if value == claim_val:
                        user.is_staff = True
                        break

        # Set superuser status
        if claims.get('superuser') is True:
            user.is_superuser = True

        user.save()
        return user

    def authenticate(self, request, remote_user=None, token=None, **kwargs):
        """
        Authenticate with OpenEdX JWT token.
        """
        if token:
            claims = self.verify_token(token)
            if not claims:
                return None
            if not self.verify_claims(claims):
                return None

            username = claims.get('preferred_username') or claims.get('username')
            if not username:
                username = claims.get('sub')

            if not username:
                return None

            # Store claims temporarily where configure_user can access them
            self._temp_claims = claims
            if request:
                request._openedx_claims = claims

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
            if request and hasattr(request, '_openedx_claims'):
                delattr(request, '_openedx_claims')

            if user and self.user_can_authenticate(user):
                return user

        return None