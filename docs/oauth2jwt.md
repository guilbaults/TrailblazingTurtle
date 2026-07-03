# Generic OAuth2 + JWT Authentication

This backend allows users to authenticate against any Identity Provider using OAuth 2.0 and JWT tokens.

## How it Works

1. **Authorization Redirect**: When a user goes to `/oauth2/login/`, they are redirected to the Identity Provider authorization endpoint.
2. **Authorization Code Grant**: After successful login at the Identity Provider, the user is redirected back to the callback view (`/oauth2/callback/`) with an authorization code.
3. **JWT Access Token Exchange**: The callback view sends a POST request to the Provider token endpoint to exchange the authorization code for a JWT access token.
4. **Token Decoding**: The custom `staffOAuth2JWTBackend` decodes the JWT payload.
   - By default, it decodes with `verify_signature=False`.
   - Alternatively, it supports signature verification (like RS256) if `JWT_OAUTH2_VERIFY_SIGNATURE` is set to `True`.
5. **User Mapping**: The backend updates user fields and roles in `configure_user`:
   - Synchronizes first name, last name, and email based on claims list.
   - Determines `is_staff` using `JWT_OAUTH2_STAFF_ATTRIBUTES`.
   - Determines `is_superuser` if the `superuser` claim is `True`.
   - Checks access restrictions via `JWT_OAUTH2_REQUIRED_ACCESS_ATTRIBUTES`.

## Configuration

To enable generic OAuth2 + JWT authentication:

1. **Register the OAuth Application in your Identity Provider** and retrieve the **Client ID** and **Client Secret**. Configure the Redirect URI:
   - **Redirect URI**: `https://<your-portal-domain>/oauth2/callback/`

2. **Enable the application and backend** in `userportal/settings/43-oauth2jwt.py` by uncommenting the setup lines:

   ```python
   JWT_OAUTH2_AUTH_ENABLED = True
   AUTHENTICATION_BACKENDS = ['userportal.authentication.staffOAuth2JWTBackend'] + AUTHENTICATION_BACKENDS
   LOGIN_URL = '/oauth2/login/'
   ```

3. **Configure your Credentials and Endpoints** in `userportal/settings/43-oauth2jwt.py`:

   ```python
   JWT_OAUTH2_PROVIDER_URL = 'https://idp.example.com'
   JWT_OAUTH2_CLIENT_ID = 'your-client-id'
   JWT_OAUTH2_CLIENT_SECRET = 'your-client-secret'
   ```

You can also specify `JWT_OAUTH2_AUTHORIZATION_URL` and `JWT_OAUTH2_TOKEN_URL` explicitly, which by default have the value of `JWT_OAUTH2_PROVIDER_URL/oauth2/authorize/` and `JWT_OAUTH2_PROVIDER_URL/oauth2/access_token/` respectively.

If needed, you can specify extra token parameters with `JWT_OAUTH2_EXTRA_TOKEN_PARAMS`. This allows to pass additional information to the OAUTH2 endpoint. For OpenEdX, define
   ```python
   JWT_OAUTH2_EXTRA_TOKEN_PARAMS = {'token_type': 'jwt'}
   ```

4. **Map access and staff roles** based on the claims structure:

   ```python
   # Only allow users with specific claims to log in
   JWT_OAUTH2_REQUIRED_ACCESS_ATTRIBUTES = []

   # Automatically set user.is_staff based on claim values
   JWT_OAUTH2_STAFF_ATTRIBUTES = [
       ('administrator', True)
   ]
   ```
