from django.test import TestCase
from unittest.mock import MagicMock, patch
from .models import ChatSession, ChatMessage, UserFeedback
from .decision_engine import DecisionEngine, TriageResult

class TriageModelsTest(TestCase):
    def test_session_creation(self):
        session = ChatSession.objects.create(chat_id="12345", platform="telegram", username="testuser")
        self.assertEqual(session.chat_id, "12345")
        self.assertEqual(session.platform, "telegram")
        self.assertFalse(session.is_cancelled())

    def test_message_creation(self):
        session = ChatSession.objects.create(chat_id="12345")
        msg = ChatMessage.objects.create(session=session, role="user", content="Hello")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello")

    def test_session_cancellation(self):
        session = ChatSession.objects.create(chat_id="12345")
        session.set_cancelled()
        self.assertTrue(session.is_cancelled())

class DecisionEngineTest(TestCase):
    def setUp(self):
        self.engine = DecisionEngine()

    @patch('triage.clients.groq_client.GroqClient.analyze_text')
    def test_analyze_text_mock(self, mock_analyze):
        # Mock the Groq client response
        mock_analyze.return_value = MagicMock(
            risk_score=8,
            summary="Threat detected",
            action="report",
            threat_type="threat",
            location="Lagos",
            advice="Stay safe",
            needs_location=False,
            detected_language="en"
        )
        
        result = self.engine.analyze_text("I am going to hurt you")
        
        self.assertIsInstance(result, TriageResult)
        self.assertEqual(result.risk_score, 8)
        self.assertEqual(result.action, "report")
        self.assertEqual(result.location, "Lagos")

    @patch('triage.clients.groq_client.GroqClient.analyze_text')
    def test_analyze_text_safe_mock(self, mock_analyze):
        mock_analyze.return_value = MagicMock(
            risk_score=2,
            summary="No threat",
            action="advise",
            threat_type="none",
            location=None,
            advice="Ignore it",
            needs_location=False
        )
        
        result = self.engine.analyze_text("Hello world")
        self.assertEqual(result.risk_score, 2)
        self.assertEqual(result.action, "advise")
