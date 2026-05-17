from datetime import datetime, timedelta
from django.contrib.auth.hashers import make_password
from tests.tests import CustomTestCase
from maas.models import MAASProvider, MAASApiKey, MAASUsageRecord, sha256_key


class MaasTestCase(CustomTestCase):
    def _create_provider(self, name='Test Provider', url='https://test.example.com', key='test-provider-key'):
        return MAASProvider.objects.create(
            name=name,
            url=url,
            key=make_password(key),
            key_hash=sha256_key(key),
            is_active=True,
        )

    def _create_api_key(self, user, name='Test Key', key='test-user-key', expires_at=None):
        return MAASApiKey.objects.create(
            user=user,
            name=name,
            key=make_password(key),
            key_hash=sha256_key(key),
            expires_at=expires_at,
            is_active=True,
        )

    # --- Web UI Tests ---

    def test_redirect_anonymous(self):
        response = self.client.get('/secure/maas/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_user_page_own(self):
        response = self.user_client.get(f'/secure/maas/{self.testuser.username}/')
        self.assertEqual(response.status_code, 200)

    def test_user_page_other(self):
        response = self.user_client.get(f'/secure/maas/{self.testadmin.username}/')
        self.assertEqual(response.status_code, 403)

    def test_admin_any_page(self):
        response = self.admin_client.get(f'/secure/maas/{self.testuser.username}/')
        self.assertEqual(response.status_code, 200)

    def test_key_new_form_get(self):
        response = self.user_client.get(f'/secure/maas/{self.testuser.username}/keys/new/')
        self.assertEqual(response.status_code, 200)

    def test_create_key_show_once(self):
        response = self.user_client.post(f'/secure/maas/{self.testuser.username}/keys/new/', {
            'name': 'Production key',
            'expires_at': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MAASApiKey.objects.filter(user=self.testuser).count(), 1)

        raw_key = response.context['raw_key']
        stored_key = MAASApiKey.objects.get(user=self.testuser)
        self.assertTrue(stored_key.is_active)
        self.assertIn('Production key', stored_key.name)

        # The raw key should appear in the creation response
        self.assertContains(response, raw_key)

        # The raw key should NOT appear in subsequent page loads
        response2 = self.user_client.get(f'/secure/maas/{self.testuser.username}/')
        self.assertNotContains(response2, raw_key)

        # The raw key should NOT appear in a new GET of the create page
        response3 = self.user_client.get(f'/secure/maas/{self.testuser.username}/keys/new/')
        self.assertNotContains(response3, raw_key)

    def test_key_revoke(self):
        api_key = self._create_api_key(self.testuser, key='revoke-test-key')
        response = self.user_client.post(f'/secure/maas/{self.testuser.username}/keys/{api_key.id}/revoke/')
        self.assertRedirects(response, f'/secure/maas/{self.testuser.username}/')
        api_key.refresh_from_db()
        self.assertFalse(api_key.is_active)

    def test_provider_admin_only(self):
        response = self.user_client.get('/secure/maas/providers/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

        response = self.admin_client.get('/secure/maas/providers/')
        self.assertEqual(response.status_code, 200)

    def test_create_provider(self):
        response = self.admin_client.post('/secure/maas/providers/new/', {
            'name': 'Test Provider',
            'url': 'https://test.example.com',
            'key': 'provider-secret-key',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MAASProvider.objects.count(), 1)

        provider = MAASProvider.objects.first()
        self.assertEqual(provider.name, 'Test Provider')
        self.assertEqual(provider.url, 'https://test.example.com')
        self.assertTrue(provider.is_active)
        self.assertIsNotNone(provider.key)

    # --- API Tests ---

    def test_post_usage_valid(self):
        self._create_provider(key='prov-secret')
        api_key = self._create_api_key(self.testuser, key='user-secret')

        response = self.client.post('/api/maas/usage/', {
            'provider_key': 'prov-secret',
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'cost': 0.005,
            'latency_ms': 450,
            'request_id': 'test-uuid-123',
        }, HTTP_AUTHORIZATION='Bearer user-secret')

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['model'], 'gpt-4o')
        self.assertEqual(data['input_tokens'], 100)
        self.assertEqual(data['output_tokens'], 250)

        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.last_used_at)
        self.assertEqual(MAASUsageRecord.objects.count(), 1)

    def test_post_usage_no_provider_key(self):
        self._create_api_key(self.testuser, key='user-secret')
        response = self.client.post('/api/maas/usage/', {
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'latency_ms': 450,
        }, HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 400)

    def test_post_usage_invalid_provider(self):
        self._create_api_key(self.testuser, key='user-secret')
        response = self.client.post('/api/maas/usage/', {
            'provider_key': 'wrong-provider-key',
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'latency_ms': 450,
        }, HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 400)

    def test_post_usage_auth_fail_no_header(self):
        response = self.client.post('/api/maas/usage/', {
            'provider_key': 'prov-secret',
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'latency_ms': 450,
        })
        self.assertEqual(response.status_code, 401)

    def test_post_usage_auth_fail_invalid_key(self):
        response = self.client.post('/api/maas/usage/', {
            'provider_key': 'prov-secret',
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'latency_ms': 450,
        }, HTTP_AUTHORIZATION='Bearer invalid-key')
        self.assertEqual(response.status_code, 401)

    def test_post_usage_revoked_key(self):
        self._create_provider(key='prov-secret')
        api_key = self._create_api_key(self.testuser, key='user-secret')
        api_key.is_active = False
        api_key.save()

        response = self.client.post('/api/maas/usage/', {
            'provider_key': 'prov-secret',
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'latency_ms': 450,
        }, HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 401)

    def test_post_usage_expired_key(self):
        self._create_provider(key='prov-secret')
        expired = datetime.now() - timedelta(days=1)
        self._create_api_key(self.testuser, key='user-secret', expires_at=expired)

        response = self.client.post('/api/maas/usage/', {
            'provider_key': 'prov-secret',
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'latency_ms': 450,
        }, HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 401)

    def test_verify_valid(self):
        provider = self._create_provider(key='prov-secret')
        self._create_api_key(self.testuser, key='user-secret')

        response = self.client.post('/api/maas/verify/', {
            'provider_key': 'prov-secret',
        }, HTTP_AUTHORIZATION='Bearer user-secret')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['user'], self.testuser.username)
        self.assertEqual(data['provider']['name'], provider.name)

    def test_verify_invalid_provider(self):
        self._create_api_key(self.testuser, key='user-secret')
        response = self.client.post('/api/maas/verify/', {
            'provider_key': 'wrong-key',
        }, HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 400)

    def test_get_usage(self):
        provider = self._create_provider(key='prov-secret')
        api_key = self._create_api_key(self.testuser, key='user-secret')

        MAASUsageRecord.objects.create(
            api_key=api_key,
            provider=provider,
            request_id='req-1',
            model='gpt-4o',
            endpoint='/v1/chat/completions',
            input_tokens=100,
            output_tokens=250,
            latency_ms=450,
        )

        response = self.client.get('/api/maas/usage/', HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['model'], 'gpt-4o')

    def test_auto_request_id(self):
        self._create_provider(key='prov-secret')
        self._create_api_key(self.testuser, key='user-secret')

        response = self.client.post('/api/maas/usage/', {
            'provider_key': 'prov-secret',
            'model': 'gpt-4o',
            'endpoint': '/v1/chat/completions',
            'input_tokens': 100,
            'output_tokens': 250,
            'latency_ms': 450,
        }, HTTP_AUTHORIZATION='Bearer user-secret')

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIsNotNone(data['request_id'])

    # --- Public Revoke Tests ---

    def test_public_revoke_valid_key(self):
        api_key = self._create_api_key(self.testuser, key='user-secret')
        response = self.client.post('/api/maas/key/revoke/', HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 200)

        api_key.refresh_from_db()
        self.assertFalse(api_key.is_active)

    def test_public_revoke_already_revoked(self):
        api_key = self._create_api_key(self.testuser, key='user-secret')
        api_key.is_active = False
        api_key.save()

        response = self.client.post('/api/maas/key/revoke/', HTTP_AUTHORIZATION='Bearer user-secret')
        self.assertEqual(response.status_code, 200)

    def test_public_revoke_invalid_key(self):
        response = self.client.post('/api/maas/key/revoke/', HTTP_AUTHORIZATION='Bearer nonexistent-key')
        self.assertEqual(response.status_code, 200)

    def test_public_revoke_no_header(self):
        response = self.client.post('/api/maas/key/revoke/')
        self.assertEqual(response.status_code, 200)
