import logging
import secrets
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from django.views import View
import requests

logger = logging.getLogger(__name__)


class OpenEdxLoginView(View):
    """View to redirect users to OpenEdX LMS for authorization."""

    def get(self, request, *args, **kwargs):
        # Generate a random state to prevent CSRF
        state = secrets.token_urlsafe(32)
        request.session['openedx_oauth_state'] = state

        lms_url = settings.OPENEDX_LMS_URL.rstrip('/')
        auth_url = f"{lms_url}/oauth2/authorize/"

        # Build authorization redirect URL
        redirect_uri = request.build_absolute_uri(reverse('openedx_callback'))

        params = {
            'response_type': 'code',
            'client_id': settings.OPENEDX_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'scope': getattr(settings, 'OPENEDX_SCOPE', 'read write email profile'),
            'state': state,
        }

        url_with_params = f"{auth_url}?{requests.compat.urlencode(params)}"
        return HttpResponseRedirect(url_with_params)


class OpenEdxCallbackView(View):
    """View to handle OpenEdX OAuth callback and authenticate the user."""

    def get(self, request, *args, **kwargs):
        # Validate state
        state = request.GET.get('state')
        session_state = request.session.pop('openedx_oauth_state', None)
        if not state or state != session_state:
            return HttpResponseBadRequest("Invalid state parameter.")

        code = request.GET.get('code')
        if not code:
            return HttpResponseBadRequest("Missing authorization code.")

        lms_url = settings.OPENEDX_LMS_URL.rstrip('/')
        token_url = f"{lms_url}/oauth2/access_token/"

        redirect_uri = request.build_absolute_uri(reverse('openedx_callback'))

        # Exchange authorization code for JWT access token
        data = {
            'grant_type': 'authorization_code',
            'client_id': settings.OPENEDX_CLIENT_ID,
            'client_secret': settings.OPENEDX_CLIENT_SECRET,
            'code': code,
            'redirect_uri': redirect_uri,
            'token_type': 'jwt',  # OpenEdX specific parameter to request a JWT
        }

        try:
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            res_data = response.json()
        except Exception as e:
            logger.error(f"Failed to exchange code for OpenEdX token: {e}")
            return HttpResponseBadRequest("Token exchange failed.")

        access_token = res_data.get('access_token')
        if not access_token:
            return HttpResponseBadRequest("No access token returned from OpenEdX.")

        # Authenticate user with the token using the custom backend
        user = authenticate(request, token=access_token)
        if user is not None:
            login(request, user)
            redirect_url = getattr(settings, 'LOGIN_REDIRECT_URL', '/')
            return HttpResponseRedirect(redirect_url)
        else:
            return HttpResponseBadRequest("Authentication failed.")
