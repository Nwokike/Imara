from django.test import TestCase, RequestFactory, override_settings
from django.core.cache import cache
from unittest import mock
from utils.ratelimit import rate_limit, get_client_ip
from utils.captcha import validate_turnstile
from django.http import HttpResponse

from utils.auth import EmailOrUsernameBackend
from django.contrib.auth.models import User

from utils.llm_router import get_llm_router
from litellm import Router

class RouterTest(TestCase):
    def test_get_llm_router_singleton(self):
        router1 = get_llm_router()
        router2 = get_llm_router()
        self.assertIsInstance(router1, Router)
        self.assertEqual(router1, router2)

class AuthBackendTest(TestCase):
    def setUp(self):
        self.backend = EmailOrUsernameBackend()
        self.user = User.objects.create_user(username="tester", email="test@imara.africa", password="password")

    def test_authenticate_by_username(self):
        user = self.backend.authenticate(None, username="tester", password="password")
        self.assertEqual(user, self.user)

    def test_authenticate_by_email(self):
        user = self.backend.authenticate(None, username="test@imara.africa", password="password")
        self.assertEqual(user, self.user)

    def test_authenticate_fail(self):
        user = self.backend.authenticate(None, username="tester", password="wrong")
        self.assertIsNone(user)

class CaptchaTest(TestCase):
    @override_settings(TURNSTILE_SECRET_KEY="test_secret", DEBUG=False)
    @mock.patch("requests.post")
    def test_validate_turnstile_success(self, mock_post):
        mock_post.return_value.json.return_value = {"success": True}
        is_valid, msg = validate_turnstile("token")
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    @override_settings(TURNSTILE_SECRET_KEY="test_secret", DEBUG=False)
    @mock.patch("requests.post")
    def test_validate_turnstile_failure(self, mock_post):
        mock_post.return_value.json.return_value = {"success": False, "error-codes": ["invalid"]}
        is_valid, msg = validate_turnstile("token")
        self.assertFalse(is_valid)
        self.assertIn("Security check failed", msg)

    @override_settings(TURNSTILE_SECRET_KEY=None, DEBUG=False)
    def test_validate_turnstile_no_key_prod(self):
        is_valid, msg = validate_turnstile("token")
        self.assertFalse(is_valid)
        self.assertIn("configuration error", msg)

class RateLimitTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def test_get_client_ip(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        self.assertEqual(get_client_ip(request), '1.2.3.4')
        
        request.META['HTTP_X_FORWARDED_FOR'] = '5.6.7.8, 1.2.3.4'
        self.assertEqual(get_client_ip(request), '5.6.7.8')

    def test_rate_limit_blocking(self):
        @rate_limit(rate="2/m", key_prefix="test")
        def mock_view(request):
            return HttpResponse("OK")

        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        # 1st request
        response = mock_view(request)
        self.assertEqual(response.status_code, 200)

        # 2nd request
        response = mock_view(request)
        self.assertEqual(response.status_code, 200)

        # 3rd request - should be blocked
        response = mock_view(request)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Rate limit exceeded', response.content.decode())

class SafetyUtilsTest(TestCase):
    def test_check_safe_word(self):
        from utils.safety import check_safe_word
        self.assertTrue(check_safe_word("STOP"))
        self.assertTrue(check_safe_word("IMARA STOP"))
        self.assertTrue(check_safe_word("  HELP ME  "))
        self.assertFalse(check_safe_word("hello"))
