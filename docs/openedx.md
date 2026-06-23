# OpenEdX OAuth + JWT Authentication

This backend allows users to authenticate against an OpenEdX LMS instance using OAuth 2.0 and JWT tokens. It is inspired by the Single Sign-On (SSO) implementation for Apache Superset in OpenEdX Aspects (`openedx_sso_security_manager.py`).

## How it Works

1. **Authorization Redirect**: When a user goes to `/openedx/login/`, they are redirected to the OpenEdX LMS authorization endpoint (`/oauth2/authorize/`).
2. **Authorization Code Grant**: After successful login at the LMS, the user is redirected back to the callback view (`/openedx/callback/`) with an authorization code.
3. **JWT Access Token Exchange**: The callback view sends a POST request to the LMS token endpoint (`/oauth2/access_token/`) specifying `token_type=jwt` as a parameter. OpenEdX LMS then issues a JSON Web Token (JWT) as the access token containing the user's claims.
4. **Token Decoding**: The custom `staffOpenEdxBackend` decodes the JWT payload. 
   - By default, it follows the `openedx_sso_security_manager` pattern of decoding with `verify_signature=False` (since the token was exchanged directly and securely server-to-server with the provider over HTTPS, validation of the signature is optional).
   - Alternatively, it supports standard RS256/HS256 signature verification if `OPENEDX_VERIFY_SIGNATURE` is set to `True`.
5. **User Mapping (Similar to SAML2)**: Similar to the SAML2 implementation, the backend updates user fields and roles in `_update_user`:
   - Synchronizes first name, last name, and email.
   - Determines `is_staff` using `OPENEDX_STAFF_ATTRIBUTES` (e.g. checking if the `administrator` claim is `True`).
   - Determines `is_superuser` if the `superuser` claim is `True`.
   - Checks access restrictions via `OPENEDX_REQUIRED_ACCESS_ATTRIBUTES`.

## Configuration

To enable OpenEdX authentication:

1. **Register the OAuth Application in OpenEdX**:
   - Log into the LMS Django Admin panel.
   - Go to **Django OAuth Toolkit** > **Applications**.
   - Create a new application:
     - **Client Type**: `Confidential`
     - **Authorization Grant Type**: `Authorization Code`
     - **Redirect URIs**: `https://<your-portal-domain>/openedx/callback/`
   - Retrieve the **Client ID** and **Client Secret**.

2. **Enable the application and backend** in `userportal/settings/43-openedx.py` by uncommenting the setup lines:

   ```python
   OPENEDX_AUTH_ENABLED = True
   AUTHENTICATION_BACKENDS = ['userportal.authentication.staffOpenEdxBackend'] + AUTHENTICATION_BACKENDS
   LOGIN_URL = '/openedx/login/'
   ```

3. **Configure your LMS Credentials and Endpoints** in `userportal/settings/43-openedx.py`:

   ```python
   OPENEDX_LMS_URL = 'https://lms.example.com'
   OPENEDX_CLIENT_ID = 'your-client-id'
   OPENEDX_CLIENT_SECRET = 'your-client-secret'
   ```

4. **Map access and staff roles** based on the returned claims:

   ```python
   # Only allow users with specific claims to log in
   OPENEDX_REQUIRED_ACCESS_ATTRIBUTES = []

   # Automatically set user.is_staff based on OpenEdX claim values
   # By default, the OpenEdX profile scope includes 'administrator': True for staff
   OPENEDX_STAFF_ATTRIBUTES = [
       ('administrator', True)
   ]
   ```
