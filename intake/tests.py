from django.urls import reverse
from django.test import TestCase, Client, override_settings
from unittest import mock
from .forms import ReportForm
from partners.models import PartnerOrganization

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
    @mock.patch('intake.views.send_email_task')
    def test_partner_inquiry_submission(self, mock_send_email, mock_turnstile):
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
        self.assertTrue(mock_send_email.called)

    def test_home_page_context(self):
        """Test that homepage context contains support resources"""
        PartnerOrganization.objects.create(
            name="Test Kenya Partner",
            jurisdiction="Kenya",
            contact_email="test@kenya.com",
            phone="123",
            is_active=True,
            is_verified=True,
        )
        PartnerOrganization.objects.create(
            name="Test Nigeria Partner",
            jurisdiction="Nigeria",
            contact_email="test@nigeria.com",
            phone="456",
            is_active=True,
            is_verified=True,
        )
        
        response = self.client.get(reverse('home'))  # Assuming 'home' is the URL name for index
        self.assertEqual(response.status_code, 200)
        self.assertIn('support_resources', response.context)
        
        resources = response.context['support_resources']
        self.assertIn('Kenya', resources)
        self.assertIn('Nigeria', resources)
        self.assertEqual(resources['Kenya'][0]['name'], "Test Kenya Partner")

    @mock.patch('utils.captcha.validate_turnstile', return_value=(True, None))
    @mock.patch('intake.views.report_processor.process_text_report')
    def test_report_form_text_submission_calls_processor(self, mock_process_text, mock_turnstile):
        mock_process_text.return_value = {"success": True, "action": "advise", "case_id": "x", "risk_score": 1}
        response = self.client.post(reverse('report_form'), {
            'message_text': 'Someone is sending threatening messages.',
            'email': 'user@example.com',
            'consent': 'on',
            'cf-turnstile-response': 'test',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/result.html')
        self.assertTrue(mock_process_text.called)

    @mock.patch('utils.captcha.validate_turnstile', return_value=(True, None))
    @mock.patch('intake.views.report_processor.process_image_report')
    def test_report_form_image_submission_calls_processor(self, mock_process_image, mock_turnstile):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image
        mock_process_image.return_value = {"success": True, "action": "advise", "case_id": "x", "risk_score": 1}
        buf = BytesIO()
        Image.new("RGB", (1, 1), color=(0, 0, 0)).save(buf, format="PNG")
        image = SimpleUploadedFile("shot.png", buf.getvalue(), content_type="image/png")
        response = self.client.post(reverse('report_form'), {
            'message_text': 'Screenshot attached.',
            'email': 'user@example.com',
            'consent': 'on',
            'cf-turnstile-response': 'test',
            'screenshot': image,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/result.html')
        self.assertTrue(mock_process_image.called)

    @mock.patch('utils.captcha.validate_turnstile', return_value=(True, None))
    @mock.patch('intake.views.report_processor.process_audio_report')
    def test_report_form_audio_submission_calls_processor(self, mock_process_audio, mock_turnstile):
        from django.core.files.uploadedfile import SimpleUploadedFile
        mock_process_audio.return_value = {"success": True, "action": "advise", "case_id": "x", "risk_score": 1}
        audio = SimpleUploadedFile("voice.ogg", b"OggS" + b"0" * 200, content_type="audio/ogg")
        response = self.client.post(reverse('report_form'), {
            'email': 'user@example.com',
            'consent': 'on',
            'cf-turnstile-response': 'test',
            'voice_note': audio,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/result.html')
        self.assertTrue(mock_process_audio.called)


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
