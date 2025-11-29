from django.test import TestCase, Client
from django.urls import reverse
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
        self.assertIn("Please provide at least one form of evidence", form.non_field_errors())

class ReportViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_report_page_loads(self):
        response = self.client.get(reverse('report_form'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/report_form.html')
