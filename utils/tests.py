from django.test import TestCase, RequestFactory
from django.core.cache import cache
from utils.ratelimit import rate_limit, get_client_ip
from django.http import HttpResponse

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
