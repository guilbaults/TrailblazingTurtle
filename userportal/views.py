import logging
import secrets
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from django.views import View
import requests

logger = logging.getLogger(__name__)


class OAuth2JWTLoginView(View):
    """View to redirect users to OAuth2 Identity Provider for authorization."""

    def get(self, request, *args, **kwargs):
        # Generate a random state to prevent CSRF
        state = secrets.token_urlsafe(32)
        request.session['oauth2_jwt_state'] = state

        auth_url = getattr(settings, 'JWT_OAUTH2_AUTHORIZATION_URL', None)
        if not auth_url:
            provider_url = getattr(settings, 'JWT_OAUTH2_PROVIDER_URL', None)
            if provider_url:
                auth_url = f"{provider_url.rstrip('/')}/oauth2/authorize/"

        if not auth_url:
            return HttpResponseBadRequest("Authorization URL is not configured.")

        # Build authorization redirect URL
        redirect_uri = request.build_absolute_uri(reverse('oauth2_jwt_callback'))

        params = {
            'response_type': 'code',
            'client_id': getattr(settings, 'JWT_OAUTH2_CLIENT_ID', None),
            'redirect_uri': redirect_uri,
            'scope': getattr(settings, 'JWT_OAUTH2_SCOPE', 'read write email profile'),
            'state': state,
        }

        url_with_params = f"{auth_url}?{requests.compat.urlencode(params)}"
        return HttpResponseRedirect(url_with_params)


class OAuth2JWTCallbackView(View):
    """View to handle OAuth2 callback and authenticate the user using JWT token."""

    def get(self, request, *args, **kwargs):
        # Validate state
        state = request.GET.get('state')
        session_state = request.session.pop('oauth2_jwt_state', None)
        if not state or state != session_state:
            return HttpResponseBadRequest("Invalid state parameter.")

        code = request.GET.get('code')
        if not code:
            return HttpResponseBadRequest("Missing authorization code.")

        token_url = getattr(settings, 'JWT_OAUTH2_TOKEN_URL', None)
        if not token_url:
            provider_url = getattr(settings, 'JWT_OAUTH2_PROVIDER_URL', None)
            if provider_url:
                token_url = f"{provider_url.rstrip('/')}/oauth2/access_token/"

        if not token_url:
            return HttpResponseBadRequest("Token URL is not configured.")

        redirect_uri = request.build_absolute_uri(reverse('oauth2_jwt_callback'))

        # Exchange authorization code for access token
        data = {
            'grant_type': 'authorization_code',
            'client_id': getattr(settings, 'JWT_OAUTH2_CLIENT_ID', None),
            'client_secret': getattr(settings, 'JWT_OAUTH2_CLIENT_SECRET', None),
            'code': code,
            'redirect_uri': redirect_uri,
        }

        extra_params = getattr(settings, 'JWT_OAUTH2_EXTRA_TOKEN_PARAMS', {})
        data.update(extra_params)

        try:
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            res_data = response.json()
        except Exception as e:
            logger.error(f"Failed to exchange code for OAuth2 token: {e}")
            return HttpResponseBadRequest("Token exchange failed.")

        access_token = res_data.get('access_token')
        if not access_token:
            return HttpResponseBadRequest("No access token returned from Identity Provider.")

        # Authenticate user with the token using the custom backend
        user = authenticate(request, token=access_token)
        if user is not None:
            login(request, user)
            redirect_url = getattr(settings, 'LOGIN_REDIRECT_URL', '/')
            return HttpResponseRedirect(redirect_url)
        else:
            return HttpResponseBadRequest("Authentication failed.")
