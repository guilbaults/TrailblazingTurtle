# OpenID Connect (OIDC) / OAuth Authentication

`mozilla-django-oidc` is supported as a lightweight OpenID Connect (OIDC) and OAuth 2.0 client authentication backend, similar to SAML2.

## How it Works

OIDC enables user authentication via an external Identity Provider (IdP) supporting OpenID Connect (such as Keycloak, Okta, Authentik, Dex, etc.).

When a user tries to access a protected page, they are redirected to the OIDC provider's login page. Upon successful authentication, they are redirected back to the portal with an authorization code. The portal exchanges this code for an ID token and access token, and queries the userinfo endpoint to fetch user details (such as first name, last name, and role/group membership claims).

The custom `staffOIDCBackend` then:
- Validates the tokens and claims.
- Generates a local username from the configured claim (e.g., `preferred_username`), cleaning the domain part if the claim is formatted as an email or principal name (e.g. `john@example.com` becomes `john`).
- Synchronizes the user's first and last names.
- Determines whether the user is active using `OIDC_REQUIRED_ACCESS_ATTRIBUTES`.
- Determines whether the user is a staff member using `OIDC_STAFF_ATTRIBUTES`.

## Configuration

To enable OIDC/OAuth authentication:

1. **Enable the application and backend** in `userportal/settings/42-oidc.py` by uncommenting the setup lines:

   ```python
   INSTALLED_APPS += ['mozilla_django_oidc']
   AUTHENTICATION_BACKENDS = ['userportal.authentication.staffOIDCBackend'] + AUTHENTICATION_BACKENDS
   LOGIN_URL = '/oidc/authenticate/'
   ```

2. **Configure your OIDC Client Credentials and Endpoints** in `userportal/settings/42-oidc.py` (or a local overrides file like `99-local.py`):

   ```python
   OIDC_OP_AUTHORIZATION_ENDPOINT = 'https://your-idp.example.com/auth'
   OIDC_OP_TOKEN_ENDPOINT = 'https://your-idp.example.com/token'
   OIDC_OP_USERINFO_ENDPOINT = 'https://your-idp.example.com/userinfo'
   OIDC_OP_JWKS_ENDPOINT = 'https://your-idp.example.com/jwks'

   OIDC_RP_CLIENT_ID = 'your-client-id'
   OIDC_RP_CLIENT_SECRET = 'your-client-secret'
   ```

3. **Map access and staff roles** based on the returned OIDC claims:

   ```python
   # Only allow users with specific claims to log in
   OIDC_REQUIRED_ACCESS_ATTRIBUTES = [
       ('email_verified', True)
   ]

   # Automatically set user.is_staff based on OIDC claim values (e.g. group membership)
   OIDC_STAFF_ATTRIBUTES = [
       ('groups', 'portal-staff')
   ]
   ```

For more details on available configurations, refer to the [mozilla-django-oidc documentation](https://mozilla-django-oidc.readthedocs.io/).
