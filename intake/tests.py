from django.urls import reverse
from django.test import TestCase, Client, override_settings
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

from .meta_service import MetaMessagingService

class MetaServiceTest(TestCase):
    @override_settings(META_PAGE_ACCESS_TOKEN='test_token')
    @mock.patch('requests.post')
    def test_send_text_message_success(self, mock_post):
        mock_post.return_value.status_code = 200
        service = MetaMessagingService()
        result = service.send_text_message("123", "Hello")
        self.assertTrue(result)
        
    @override_settings(META_PAGE_ACCESS_TOKEN='test_token')
    @mock.patch('requests.post')
    def test_send_typing_indicator(self, mock_post):
        mock_post.return_value.status_code = 200
        service = MetaMessagingService()
        result = service.send_typing_indicator("123")
        self.assertTrue(result)

    @override_settings(META_PAGE_ACCESS_TOKEN='test_token')
    @mock.patch('requests.post')
    def test_send_buttons_success(self, mock_post):
        mock_post.return_value.status_code = 200
        service = MetaMessagingService()
        result = service.send_message_with_buttons("123", "Choose", [{"title": "Yes", "payload": "Y"}])
        self.assertTrue(result)

from .webhook_service import TelegramProcessor, MetaProcessor

class WebhookProcessorTest(TestCase):
    def setUp(self):
        self.tg_processor = TelegramProcessor()
        self.meta_processor = MetaProcessor()

    @mock.patch('intake.webhook_service.decision_engine.chat_orchestration')
    def test_telegram_process_update_text(self, mock_orch):
        mock_orch.return_value = mock.MagicMock(action="ADVISE", risk_score=2, summary="OK", advice="Safe")
        data = {
            "message": {
                "chat": {"id": "123"},
                "from": {"username": "testuser"},
                "text": "Hello"
            }
        }
        with mock.patch('intake.webhook_service.TelegramProcessor.send_message_sync'):
            self.tg_processor.process_update(data)
        self.assertTrue(mock_orch.called)

    @mock.patch('intake.webhook_service.decision_engine.chat_orchestration')
    @mock.patch('intake.webhook_service.meta_messenger.send_text_message')
    def test_meta_process_event_text(self, mock_send, mock_orch):
        mock_orch.return_value = mock.MagicMock(action="ADVISE", risk_score=2, summary="OK", advice="Safe")
        event = {
            "sender": {"id": "456"},
            "message": {"text": "Help"}
        }
        self.meta_processor.handle_messaging_event(event, "messenger")
        self.assertTrue(mock_orch.called)
        self.assertTrue(mock_send.called)

from .services import ReportProcessor

class ReportProcessorTest(TestCase):
    def setUp(self):
        self.processor = ReportProcessor()

    @mock.patch('intake.services.decision_engine.web_orchestration')
    def test_process_text_report(self, mock_web):
        mock_web.return_value = mock.MagicMock(
            risk_score=8, action="REPORT", location="Nigeria", 
            summary="Serious", forensic_hash="abc", to_dict=lambda: {}
        )
        # Mock dispatch to prevent email sending
        with mock.patch.object(self.processor, '_dispatch_to_partner', return_value={"success": True}):
            result = self.processor.process_text_report("Help", reporter_email="user@test.com")
            
        self.assertEqual(result["action"], "report")
        self.assertTrue(IncidentReport.objects.filter(reporter_email="user@test.com").exists())

    @mock.patch('intake.services.decision_engine.analyze_image')
    def test_process_image_report(self, mock_vision):
        mock_res = mock.MagicMock(
            risk_score=5, action="ADVISE", location="Kenya", 
            summary="OK", extracted_text="Extracted", to_dict=lambda: {}
        )
        mock_res.should_report = False
        mock_vision.return_value = mock_res
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = SimpleUploadedFile("test.jpg", b"fake content", content_type="image/jpeg")
        
        result = self.processor.process_image_report(img, source="web")
        self.assertEqual(result["action"], "advise")
        self.assertEqual(result["extracted_text"], "Extracted")
