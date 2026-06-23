from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client


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


from django.test import override_settings
from django.urls import reverse
from unittest.mock import patch, MagicMock

class OpenEdxAuthTestCase(TestCase):
    databases = '__all__'

    @override_settings(
        OPENEDX_AUTH_ENABLED=True,
        OPENEDX_LMS_URL='https://lms.example.com',
        OPENEDX_CLIENT_ID='test-client-id',
        OPENEDX_CLIENT_SECRET='test-client-secret',
        OPENEDX_VERIFY_SIGNATURE=False,
    )
    def test_login_redirect(self):
        client = Client()
        response = client.get(reverse('openedx_login'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('https://lms.example.com/oauth2/authorize/'))
        self.assertIn('client_id=test-client-id', response['Location'])
        self.assertIn('response_type=code', response['Location'])

    @override_settings(
        OPENEDX_AUTH_ENABLED=True,
        OPENEDX_LMS_URL='https://lms.example.com',
        OPENEDX_CLIENT_ID='test-client-id',
        OPENEDX_CLIENT_SECRET='test-client-secret',
        OPENEDX_VERIFY_SIGNATURE=False,
        OPENEDX_STAFF_ATTRIBUTES=[('administrator', True)],
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
            'username': 'openedxuser',
            'email': 'openedxuser@example.com',
            'given_name': 'Open',
            'family_name': 'EdX',
            'administrator': True,
            'superuser': False,
        }

        # Set session state
        client = Client()
        session = client.session
        session['openedx_oauth_state'] = 'teststate'
        session.save()

        response = client.get(reverse('openedx_callback'), {'state': 'teststate', 'code': 'testcode'})
        
        # Verify redirect to home
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

        # Verify user was created
        User = get_user_model()
        user = User.objects.get(username='openedxuser')
        self.assertEqual(user.email, 'openedxuser@example.com')
        self.assertEqual(user.first_name, 'Open')
        self.assertEqual(user.last_name, 'EdX')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

