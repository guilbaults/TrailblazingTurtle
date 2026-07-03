# OIDC Settings using mozilla-django-oidc
# For documentation, see docs/oidc.md

# To enable OIDC authentication, uncomment these lines:
# INSTALLED_APPS += ['mozilla_django_oidc']
# MIDDLEWARE += ['mozilla_django_oidc.middleware.SessionRefresh'] # Optional, for token expiration/session refresh
# AUTHENTICATION_BACKENDS = ['userportal.authentication.staffOIDCBackend'] + AUTHENTICATION_BACKENDS
# LOGIN_URL = '/oidc/authenticate/'
# LOGIN_REDIRECT_URL = '/'
# LOGOUT_REDIRECT_URL = '/'

# if behind a proxy
# USE_X_FORWARDED_HOST = True
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# for the case of multiple proxies, this is needed
# MIDDLEWARE = ['multipleproxy.middleware.MultipleProxyMiddleware'] + MIDDLEWARE


# OpenID Connect Provider configurations:
OIDC_OP_AUTHORIZATION_ENDPOINT = 'https://your-idp.example.com/auth'
OIDC_OP_TOKEN_ENDPOINT = 'https://your-idp.example.com/token'
OIDC_OP_USER_ENDPOINT = 'https://your-idp.example.com/userinfo'
OIDC_OP_JWKS_ENDPOINT = 'https://your-idp.example.com/jwks'

OIDC_RP_CLIENT_ID = 'your-client-id'
OIDC_RP_CLIENT_SECRET = 'your-client-secret'

# Algorithm for verifying JWT signatures (e.g. RS256, HS256)
OIDC_RP_SIGN_ALGO = 'RS256'

# Custom scopes if needed
OIDC_RP_SCOPES = 'openid email profile'

# If set to True, a new Django user will be created if one does not exist
OIDC_CREATE_USER = True

# Username claim to use for matching the LDAP username.
# Our custom staffOIDCBackend cleans the domain part if the claim contains an email or full principal name.
OIDC_USERNAME_CLAIM = 'preferred_username'

# Use this to define if the user can login.
# List of tuples of (claim_name, expected_value). All must match.
OIDC_REQUIRED_ACCESS_ATTRIBUTES = []

# Use this to assign the staff role based on claims returned by OIDC.
# List of tuples of (claim_name, expected_value). If ANY matches, the user is_staff will be set to True.
OIDC_STAFF_ATTRIBUTES = [
    ('groups', 'staff')
]
