from django.test import Client, override_settings, TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from unittest.mock import patch, MagicMock


class CustomTestCase(TestCase):
    databases = '__all__'

    @classmethod
    def setUp(self):
        self.testuser = get_user_model().objects.create_user(
            username=settings.TESTS_USER,
            password='userpassword')
        self.testadmin = get_user_model().objects.create_superuser(
            username=settings.TESTS_ADMIN,
            password='adminpassword')

        self.user_client = Client()
        self.user_client.login(username=settings.TESTS_USER, password='userpassword')

        self.admin_client = Client()
        self.admin_client.login(username=settings.TESTS_ADMIN, password='adminpassword')

    def assertJSONKeys(self, response, keys):
        self.assertEqual(set(response.json().keys()), set(keys))


class OAuth2JWTAuthTestCase(TestCase):
    databases = '__all__'

    @override_settings(
        JWT_OAUTH2_AUTH_ENABLED=True,
        JWT_OAUTH2_PROVIDER_URL='https://idp.example.com',
        JWT_OAUTH2_CLIENT_ID='test-client-id',
        JWT_OAUTH2_CLIENT_SECRET='test-client-secret',
        JWT_OAUTH2_VERIFY_SIGNATURE=False,
    )
    def test_login_redirect(self):
        client = Client()
        response = client.get(reverse('oauth2_jwt_login'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('https://idp.example.com/oauth2/authorize/'))
        self.assertIn('client_id=test-client-id', response['Location'])
        self.assertIn('response_type=code', response['Location'])

    @override_settings(
        JWT_OAUTH2_AUTH_ENABLED=True,
        JWT_OAUTH2_PROVIDER_URL='https://idp.example.com',
        JWT_OAUTH2_CLIENT_ID='test-client-id',
        JWT_OAUTH2_CLIENT_SECRET='test-client-secret',
        JWT_OAUTH2_VERIFY_SIGNATURE=False,
        JWT_OAUTH2_STAFF_ATTRIBUTES=[('administrator', True)],
        AUTHENTICATION_BACKENDS=['userportal.authentication.staffOAuth2JWTBackend'] + settings.AUTHENTICATION_BACKENDS,
    )
    @patch('requests.post')
    @patch('jwt.decode')
    def test_callback_success(self, mock_jwt_decode, mock_post):
        # Mock requests.post for token exchange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'fake-jwt-token'}
        mock_post.return_value = mock_response

        # Mock jwt.decode for payload extraction
        mock_jwt_decode.return_value = {
            'username': 'oauth2user',
            'email': 'oauth2user@example.com',
            'given_name': 'OAuth2',
            'family_name': 'User',
            'administrator': True,
            'superuser': False,
        }

        # Set session state
        client = Client()
        session = client.session
        session['oauth2_jwt_state'] = 'teststate'
        session.save()

        response = client.get(reverse('oauth2_jwt_callback'), {'state': 'teststate', 'code': 'testcode'})

        # Verify redirect to home
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

        # Verify user was created
        User = get_user_model()
        user = User.objects.get(username='oauth2user')
        self.assertEqual(user.email, 'oauth2user@example.com')
        self.assertEqual(user.first_name, 'OAuth2')
        self.assertEqual(user.last_name, 'User')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
