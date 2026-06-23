# OpenEdX OAuth + JWT Settings
# For documentation, see docs/openedx.md

# To enable OpenEdX authentication, uncomment these lines:
# OPENEDX_AUTH_ENABLED = True
# AUTHENTICATION_BACKENDS = ['userportal.authentication.staffOpenEdxBackend'] + AUTHENTICATION_BACKENDS
# LOGIN_URL = '/openedx/login/'
# LOGIN_REDIRECT_URL = '/'
# LOGOUT_REDIRECT_URL = '/'

# OpenEdX LMS Provider configurations:
OPENEDX_LMS_URL = 'https://lms.example.com'
OPENEDX_CLIENT_ID = 'your-client-id'
OPENEDX_CLIENT_SECRET = 'your-client-secret'

# JWT signature verification options
# By default, verify_signature can be False when using server-to-server token exchange,
# similar to openedx_sso_security_manager in tutor-contrib-aspects.
OPENEDX_VERIFY_SIGNATURE = False
OPENEDX_SIGN_ALGO = 'RS256'

# Scope to request from OpenEdX
OPENEDX_SCOPE = 'read write email profile'

# Create Django user if they don't exist (similar to SAML_CREATE_UNKNOWN_USER)
OPENEDX_CREATE_UNKNOWN_USER = True

# List of tuples of (claim_name, expected_value) for access requirements (must all match)
OPENEDX_REQUIRED_ACCESS_ATTRIBUTES = []

# List of tuples of (claim_name, expected_value). If ANY matches, user.is_staff will be True.
# Under OpenEdX profile scope, 'administrator' is set to True for staff users.
OPENEDX_STAFF_ATTRIBUTES = [
    ('administrator', True)
]
