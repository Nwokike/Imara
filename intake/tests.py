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

