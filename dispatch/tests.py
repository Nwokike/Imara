from django.test import TestCase
from cases.models import IncidentReport
from .models import DispatchLog

class DispatchLogTest(TestCase):
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
