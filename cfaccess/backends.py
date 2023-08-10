from typing import Any, Optional, Union
from django.contrib.auth.backends import RemoteUserBackend, ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import User
from django.http.request import HttpRequest

from django.conf import settings

from django.contrib.auth import get_user_model
UserModel = get_user_model()

from ccldap.models import LdapUser

class CloudflareAccessLDAPBackend(ModelBackend):

    create_unknown_user = True

    def authenticate(self, request: HttpRequest, cloudflare_user: str, jwt_data=None, **kwargs) -> Union[User, None]:
        if not cloudflare_user:
            return
        
        user = None
        created = False
        username = self.clean_username(cloudflare_user)

        # Temporary fix to restrict CILogon
        if cloudflare_user.split('@')[1] != 'alliancecan.ca':
            return

        if self.create_unknown_user:
            user, created = UserModel._default_manager.get_or_create(
                **{UserModel.USERNAME_FIELD: username}
            )
        else:
            try:
                user = UserModel._default_manager.get_by_natural_key(username)
            except UserModel.DoesNotExist:
                pass

        user = self.configure_user(request, user, created=created, jwt_data=jwt_data)
        return user if self.user_can_authenticate(user) else None

    def configure_user(self, request: HttpRequest, user: User, created=True, jwt_data=None) -> User:
        ldapuser = LdapUser.objects.get(username=user.username)

        try:
            user.first_name = ldapuser.given_name
        except:
            user.first_name = ''
        
        try:
            user.last_name = ldapuser.surname
        except:
            user.last_name = ''

        if jwt_data:
            has_staff_attr = False
            for attribute, value in settings.CF_ACCESS_CONFIG['staff_attributes']:
                if (attribute in jwt_data['custom']):
                    if (type(jwt_data['custom'][attribute]) == list) and (value in jwt_data['custom'][attribute]):
                        has_staff_attr = True
                    elif (type(jwt_data['custom'][attribute]) == str) and (value == jwt_data['custom'][attribute]):
                        has_staff_attr = True

            user.is_staff = has_staff_attr

        user.save()

        return user

    def clean_username(self, username):
        return username.split('@')[0]