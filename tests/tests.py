import json

from django.test import Client, override_settings, RequestFactory, SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from unittest.mock import patch, MagicMock
from prometheus_api_client.exceptions import PrometheusApiClientException
from requests.exceptions import ConnectionError
from urllib3.util.retry import Retry

from userportal.common import Prometheus
from userportal.exceptions import PrometheusUnavailable
from userportal.logging_filters import SkipHandledPrometheusUnavailable
from userportal.middleware import PrometheusUnavailableMiddleware


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


class PrometheusFailureTestCase(SimpleTestCase):
    @patch('userportal.common.PrometheusConnect')
    def test_connection_failure_is_wrapped(self, prometheus_connect):
        prometheus_connect.return_value.custom_query_range.side_effect = ConnectionError('Connection refused')
        prometheus = Prometheus({'url': 'http://prometheus:9090', 'headers': {}})

        with self.assertRaises(PrometheusUnavailable):
            prometheus.query_prometheus_multiple('up', MagicMock(), MagicMock())

        call_kwargs = prometheus_connect.call_args.kwargs
        self.assertEqual(call_kwargs['url'], 'http://prometheus:9090')
        self.assertEqual(call_kwargs['headers'], {})
        self.assertEqual(call_kwargs['timeout'], 5)
        self.assertIsInstance(call_kwargs['retry'], Retry)
        self.assertEqual(call_kwargs['retry'].total, 0)

    @patch('userportal.common.PrometheusConnect')
    def test_server_error_is_wrapped(self, prometheus_connect):
        prometheus_connect.return_value.custom_query.side_effect = PrometheusApiClientException(
            "HTTP Status Code 503 (b'Service Unavailable')"
        )
        prometheus = Prometheus({'url': 'http://prometheus:9090', 'headers': {}})

        with self.assertRaises(PrometheusUnavailable) as raised:
            prometheus.query_last('up')

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(str(raised.exception), "Prometheus instant query failed")

    @patch('userportal.common.PrometheusConnect')
    def test_client_error_is_not_wrapped(self, prometheus_connect):
        prometheus_connect.return_value.custom_query_range.side_effect = PrometheusApiClientException(
            "HTTP Status Code 400 (b'Bad Request')"
        )
        prometheus = Prometheus({'url': 'http://prometheus:9090', 'headers': {}})

        with self.assertRaises(PrometheusApiClientException):
            prometheus.query_prometheus_multiple('invalid query', MagicMock(), MagicMock())

    def test_json_request_gets_service_unavailable_response(self):
        request = RequestFactory().get('/logins/graph/load/login1.json')
        middleware = PrometheusUnavailableMiddleware(lambda request: None)

        response = middleware.process_exception(
            request,
            PrometheusUnavailable('Prometheus range query failed'),
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.content), {'error': 'Metrics are temporarily unavailable'})
        self.assertEqual(response['Retry-After'], '30')
        self.assertTrue(request.prometheus_unavailable)

    @patch('userportal.middleware._', return_value='Les métriques sont temporairement indisponibles')
    def test_service_unavailable_response_is_translated(self, gettext):
        request = RequestFactory().get('/logins/graph/load/login1.json')
        middleware = PrometheusUnavailableMiddleware(lambda request: None)

        response = middleware.process_exception(
            request,
            PrometheusUnavailable('Prometheus range query failed'),
        )

        self.assertEqual(
            json.loads(response.content),
            {'error': 'Les métriques sont temporairement indisponibles'},
        )
        gettext.assert_called_once_with('Metrics are temporarily unavailable')

    def test_duplicate_django_request_log_is_filtered(self):
        request = RequestFactory().get('/logins/graph/load/login1.json')
        request.prometheus_unavailable = True
        record = MagicMock(status_code=503, request=request)

        self.assertFalse(SkipHandledPrometheusUnavailable().filter(record))


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
