from django.urls import reverse
from django.test import TestCase, Client, override_settings
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

    def test_partner_inquiry_submission(self):
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
