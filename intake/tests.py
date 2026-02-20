from django.urls import reverse
from django.test import TestCase, Client
from unittest import mock
from .forms import ReportForm
from cases.models import IncidentReport

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

class IntakeViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_pages_load(self):
        pages = ['report_form', 'partner', 'consent', 'policies', 'contact']
        for page in pages:
            response = self.client.get(reverse(page))
            self.assertEqual(response.status_code, 200, f"{page} failed to load")

    @mock.patch('triage.tasks.process_web_report_task')
    @mock.patch('utils.captcha.validate_turnstile', return_value=(True, None))
    def test_report_form_submission_enqueues_task(self, mock_turnstile, mock_task):
        """Test that submitting the web form creates an incident and enqueues analysis."""
        data = {
            'message_text': 'Emergency help needed',
            'email': 'victim@example.com',
            'consent': 'on',
            'cf-turnstile-response': 'valid_token',
        }
        response = self.client.post(reverse('report_form'), data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'intake/result.html')
        
        # Verify database record
        incident = IncidentReport.objects.get(reporter_email='victim@example.com')
        self.assertEqual(incident.source, 'web')
        
        # Verify task enqueued
        mock_task.enqueue.assert_called_once_with(incident.pk)

    def test_report_status_endpoint(self):
        """Test the real-time status polling endpoint."""
        incident = IncidentReport.objects.create(
            source='web', 
            analysis_status='PROCESSING',
            reasoning_log=[{"agent": "Sentinel", "detail": "Checking..."}]
        )
        url = reverse('report_status', kwargs={'case_id': incident.case_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'PROCESSING')

class WebhookTests(TestCase):
    @mock.patch('triage.tasks.process_telegram_update_task')
    def test_telegram_webhook_enqueues_task(self, mock_task):
        payload = {
            "message": {
                "chat": {"id": 123},
                "from": {"username": "testuser"},
                "text": "Hello"
            }
        }
        url = reverse('telegram_webhook')
        from django.conf import settings
        response = self.client.post(
            url, 
            data=payload, 
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=settings.TELEGRAM_SECRET_TOKEN
        )
        self.assertEqual(response.status_code, 200)
        mock_task.enqueue.assert_called_once()
