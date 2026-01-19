from django.urls import reverse
from directory.models import AuthorityContact
from django.test import TestCase, Client, override_settings
from unittest import mock
from .forms import ReportForm

class ReportFormTest(TestCase):
    def test_valid_form_text_only(self):
        """Form should be valid with just text"""
        data = {
            'message_text': 'I am being harassed',
            'email': 'user@example.com',
            'consent': True
        }
        form = ReportForm(data=data)
        self.assertTrue(form.is_valid())

    def test_invalid_form_no_evidence(self):
        """Form should be INVALID if no text, screenshot, or audio is provided"""
        data = {
            'email': 'user@example.com',
            'consent': True
        }
        form = ReportForm(data=data)
        self.assertFalse(form.is_valid())
        errors = str(form.non_field_errors())
        self.assertIn("Please provide at least one form of evidence", errors)

@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class IntakeViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_report_page_loads(self):
        response = self.client.get(reverse('report_form'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/report_form.html')

    def test_partner_page_loads(self):
        response = self.client.get(reverse('partner'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/partner.html')

    def test_consent_page_loads(self):
        response = self.client.get(reverse('consent'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/consent.html')

    def test_policies_page_loads(self):
        response = self.client.get(reverse('policies'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/policies.html')

    @mock.patch('utils.captcha.validate_turnstile', return_value=(True, None))
    def test_partner_inquiry_submission(self, mock_turnstile):
        """Test POST request to partner form"""
        data = {
            'organization_name': 'Test NGO',
            'contact_name': 'Jane Doe',
            'email': 'jane@example.com',
            'country': 'Kenya',
            'partnership_type': 'outreach',
            'org_type': 'ngo',
            'message': 'We want to partner.'
        }
        response = self.client.post(reverse('partner'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['success'])

    def test_home_page_context(self):
        """Test that homepage context contains support resources"""
        # Create test contacts
        AuthorityContact.objects.create(
            agency_name="Test Kenya Agency",
            jurisdiction_name="Kenya",
            email="test@kenya.com",
            phone="123",
            priority=10
        )
        AuthorityContact.objects.create(
            agency_name="Test Nigeria Agency",
            jurisdiction_name="Nigeria",
            email="test@nigeria.com",
            phone="456",
            priority=10
        )
        
        response = self.client.get(reverse('home'))  # Assuming 'home' is the URL name for index
        self.assertEqual(response.status_code, 200)
        self.assertIn('support_resources', response.context)
        
        resources = response.context['support_resources']
        self.assertIn('Kenya', resources)
        self.assertIn('Nigeria', resources)
        self.assertEqual(resources['Kenya'][0].agency_name, "Test Kenya Agency")


@override_settings(
    SECURE_SSL_REDIRECT=False,
    META_VERIFY_TOKEN='test_verify_token_123',
    META_APP_SECRET='test_app_secret_456',
    META_PAGE_ACCESS_TOKEN='test_access_token_789',
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class MetaWebhookTests(TestCase):
    """Tests for the Meta (Facebook/Instagram) Webhook integration."""
    
    def setUp(self):
        self.client = Client()
        self.webhook_url = reverse('meta_webhook')
    
    def test_meta_webhook_verification_success(self):
        """Test that webhook verification returns challenge on valid token."""
        response = self.client.get(self.webhook_url, {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'test_verify_token_123',
            'hub.challenge': 'CHALLENGE_ACCEPTED'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'CHALLENGE_ACCEPTED')
    
    def test_meta_webhook_verification_invalid_token(self):
        """Test that webhook verification fails with wrong token."""
        response = self.client.get(self.webhook_url, {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'wrong_token',
            'hub.challenge': 'CHALLENGE'
        })
        self.assertEqual(response.status_code, 403)
    
    def test_meta_webhook_verification_missing_params(self):
        """Test that webhook verification fails without required params."""
        response = self.client.get(self.webhook_url)
        self.assertEqual(response.status_code, 400)
    
    def _create_signature(self, payload: bytes) -> str:
        """Helper to create valid X-Hub-Signature-256."""
        import hmac
        import hashlib
        signature = hmac.new(
            b'test_app_secret_456',
            payload,
            hashlib.sha256
        ).hexdigest()
        return f'sha256={signature}'
    
    def test_meta_webhook_post_invalid_signature(self):
        """Test that POST with invalid signature is rejected."""
        payload = b'{"object": "page", "entry": []}'
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=invalid_signature'
        )
        self.assertEqual(response.status_code, 403)
    
    def test_meta_webhook_post_valid_signature(self):
        """Test that POST with valid signature is accepted."""
        payload = b'{"object": "page", "entry": []}'
        signature = self._create_signature(payload)
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'EVENT_RECEIVED')
    
    def test_meta_webhook_instagram_object(self):
        """Test that Instagram object type is handled."""
        payload = b'{"object": "instagram", "entry": []}'
        signature = self._create_signature(payload)
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature
        )
        self.assertEqual(response.status_code, 200)
    
    def test_meta_webhook_unknown_object(self):
        """Test that unknown object type returns 404."""
        payload = b'{"object": "unknown", "entry": []}'
        signature = self._create_signature(payload)
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature
        )
        self.assertEqual(response.status_code, 404)
