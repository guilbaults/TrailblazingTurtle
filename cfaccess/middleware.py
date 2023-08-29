from django.http import HttpResponse, JsonResponse, HttpResponseForbidden, HttpRequest
from django.conf import settings

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User

from cfaccess.backends import CloudflareAccessLDAPBackend

import requests
import jwt
import json

import time

class CloudflareAccessLDAPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def clean_username(self, username):
        backend = CloudflareAccessLDAPBackend()
        return backend.clean_username(username)
    
    def __call__(self, request: HttpRequest):
        """
        This middleware will check for a valid Cloudflare Access JWT.

        If valid JWT is NOT presented, and Cloudflare Access enforcement
        is enabled, a 403 Forbidden will be returned for all requests.

        If a valid JWT is NOT presented, and Cloudflare Access enforcement
        is disabled, the session will be allowed to continue, weather it is
        authenticated or not.

        If a valid JWT is presented, and matches the currently authenticated
        user, the session is allowed to continue.
        
        If a valid JWT is presented, and the user is not currently
        authenticated, this middleware will attempt to authenticate the
        user.

        If a valid JWT is presented, but it does not match the currently
        authenticated user, the session will be logged out and
        authentication will be attempted with the new user.
        """

        # check for no JWT
        if "CF_Authorization" not in request.COOKIES:
            return self._handle_no_token(request)
        
        # validate presented JWT
        # ts = time.time()
        token = request.COOKIES["CF_Authorization"]
        keys = self._get_public_keys()
        policy_aud = settings.CF_ACCESS_CONFIG['policy_aud']

        jwt_data = self._validate_JWT(token, keys, policy_aud)
        
        # handle as no / invalid token
        if not jwt_data:
            return self._handle_no_token(request)

        jwt_username = jwt_data[settings.CF_ACCESS_CONFIG['username_attribute']]


        # if the user is authenticated, but does not match the token, logout the previous
        # user and login the new session
        if request.user.get_username() != self.clean_username(jwt_username):
            logout(request)

        # We have a valid JWT, check if the user is not currently authenticated, if so,
        # login the user to their session
        if not request.user.is_authenticated:
            user = authenticate(request, cloudflare_user=jwt_username, jwt_data=jwt_data)
            request.user = user
            login(request, user)

        # The user is already authenticated as the correct user, proceed with session
        return self.get_response(request)


    def _handle_no_token(self, request):
        if settings.CF_ACCESS_CONFIG['enforce_cloudflare_access']:
            return HttpResponseForbidden()
        else:
            return self.get_response(request)
            

    def _validate_JWT(self, jwt_token, keys, aud):
        """
        Checks if provided Cloudflare Access JWT is valid. A JWT is determined
        to be valid if it is signed by any of the provided keys and the JWT 
        "aud" matches the provided "aud".

        if the JWT is valid, it's payload is returned.

        A invalid token will return None
        """
        for key in keys:
            try:
                # decode returns the claims that has the email when needed
                token_data = jwt.decode(jwt_token, key=key, audience=aud, algorithms=['RS256'])
                return token_data
            except:
                pass

    def _get_public_keys(self):
        """
        Returns:
            List of RSA public keys usable by PyJWT.
        """
        request_url = "{}/cdn-cgi/access/certs".format(settings.CF_ACCESS_CONFIG['team_domain'])

        r = requests.get(request_url)
        public_keys = []
        jwk_set = r.json()
        for key_dict in jwk_set['keys']:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_dict))
            public_keys.append(public_key)
        return public_keys

