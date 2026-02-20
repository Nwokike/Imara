from django.test import TestCase, TransactionTestCase, override_settings
from unittest import mock
from asgiref.sync import async_to_sync
from cases.models import IncidentReport
from .models import DispatchLog
from .tasks import send_email_task

class DispatchLogTest(TransactionTestCase):
    def setUp(self):
        self.report = IncidentReport.objects.create(source='web')

    def test_log_creation(self):
        log = DispatchLog.objects.create(
            incident=self.report,
            recipient_email="police@gov.ng",
            subject="Test Alert",
            status="sent"
        )
        self.assertEqual(log.status, "sent")
        self.assertEqual(str(log), "Dispatch to police@gov.ng - sent")


class BrevoTaskTests(TransactionTestCase):
    @override_settings(BREVO_API_KEY="test_key")
    @mock.patch("httpx.AsyncClient.post")
    def test_send_email_task_updates_dispatch_log_and_incident(self, mock_post):
        """Test that the async send_email_task correctly updates DB state."""
        incident = IncidentReport.objects.create(source='web')
        log = DispatchLog.objects.create(
            incident=incident,
            recipient_email="partner@example.com",
            subject="Test Alert",
            status="pending"
        )

        # Properly mock httpx response for async
        mock_response = mock.MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"messageId": "brevo-msg-1"}
        
        # httpx .post is an async method
        async def mock_post_coro(*args, **kwargs):
            return mock_response
        
        mock_post.side_effect = mock_post_coro

        payload = {
            "sender": {"name": "Imara", "email": "noreply@imara.africa"},
            "to": [{"email": "partner@example.com"}],
            "subject": "Test",
            "htmlContent": "<p>hi</p>",
        }

        # Call the underlying function directly
        async_to_sync(send_email_task.func)(payload, dispatch_log_id=log.pk, incident_id=incident.pk)

        # Refresh and verify
        log.refresh_from_db()
        self.assertEqual(log.status, "sent")
        self.assertEqual(log.brevo_message_id, "brevo-msg-1")

        incident.refresh_from_db()
        self.assertIsNotNone(incident.dispatched_at)
        self.assertEqual(incident.dispatched_to, "partner@example.com")

class BackupTaskTests(TestCase):
    @mock.patch("sqlite3.connect")
    @mock.patch("boto3.client")
    @mock.patch("os.remove")
    @mock.patch("dispatch.tasks.Path.exists", return_value=True)
    def test_backup_database_task(self, mock_exists, mock_remove, mock_boto, mock_sqlite):
        """Test the native database backup lifecycle."""
        from .tasks import backup_database_task
        
        # Setup mocks
        mock_s3 = mock.MagicMock()
        mock_boto.return_value = mock_s3
        
        with override_settings(DATABASES={'default': {'NAME': 'test.db'}}):
            backup_database_task.func()
            
        # Verify SQLite interaction
        self.assertEqual(mock_sqlite.call_count, 2) # src and dst
        
        # Verify S3 interaction
        self.assertTrue(mock_s3.upload_file.called)
        
        # Verify cleanup
        self.assertTrue(mock_remove.called)
