# Generic OAuth2 + JWT Settings
# For documentation, see docs/oauth2jwt.md

# To enable generic OAuth2 + JWT authentication, uncomment these lines:
# JWT_OAUTH2_AUTH_ENABLED = True
# AUTHENTICATION_BACKENDS = ['userportal.authentication.staffOAuth2JWTBackend'] + AUTHENTICATION_BACKENDS
# LOGIN_URL = '/oauth2/login/'
# LOGIN_REDIRECT_URL = '/'
# LOGOUT_REDIRECT_URL = '/'

# Provider configuration:
JWT_OAUTH2_PROVIDER_URL = 'https://idp.example.com'
JWT_OAUTH2_CLIENT_ID = 'your-client-id'
JWT_OAUTH2_CLIENT_SECRET = 'your-client-secret'

# JWT signature verification options
# By default, verify_signature can be False when using server-to-server token exchange
JWT_OAUTH2_VERIFY_SIGNATURE = False
JWT_OAUTH2_SIGN_ALGO = 'RS256'

# Scope to request from the Identity Provider
JWT_OAUTH2_SCOPE = 'read write email profile'

# Create Django user if they don't exist
JWT_OAUTH2_CREATE_UNKNOWN_USER = True

# List of tuples of (claim_name, expected_value) for access requirements (must all match)
JWT_OAUTH2_REQUIRED_ACCESS_ATTRIBUTES = []

# List of tuples of (claim_name, expected_value). If ANY matches, user.is_staff will be True.
JWT_OAUTH2_STAFF_ATTRIBUTES = [
    ('administrator', True)
]
