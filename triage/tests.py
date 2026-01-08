from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
from .decision_engine import decision_engine
from .models import ChatSession

class DecisionEngineTest(TestCase):
    
    @patch('triage.clients.groq_client.GroqClient.analyze_text')
    def test_analyze_text_high_risk_with_location(self, mock_analyze):
        """Test that high risk text with location returns REPORT action"""
        mock_response = MagicMock()
        mock_response.risk_score = 9
        mock_response.action = 'REPORT'
        mock_response.summary = 'Death threat in Lagos'
        mock_response.threat_type = 'threat'
        mock_response.location = 'Lagos'
        mock_response.advice = None
        
        mock_analyze.return_value = mock_response

        # Context can be None or a list
        result = decision_engine.analyze_text("I will kill you in Lagos", [])

        self.assertEqual(result.risk_score, 9)
        self.assertTrue(result.should_report)
        self.assertEqual(result.location, 'Lagos')

    @patch('triage.clients.groq_client.GroqClient.analyze_text')
    def test_analyze_text_high_risk_no_location(self, mock_analyze):
        """Test that high risk text WITHOUT location returns ASK_LOCATION"""
        mock_response = MagicMock()
        mock_response.risk_score = 8
        mock_response.action = 'ASK_LOCATION' # Engine usually upgrades to this if loc is unknown
        mock_response.location = 'Unknown'
        
        mock_analyze.return_value = mock_response

        result = decision_engine.analyze_text("I will find you")

        self.assertTrue(result.needs_location)
        self.assertFalse(result.should_report) # Not yet

    @patch('triage.clients.groq_client.GroqClient.analyze_text')
    def test_analyze_text_low_risk(self, mock_analyze):
        """Test that low risk text returns ADVISE"""
        mock_response = MagicMock()
        mock_response.risk_score = 2
        mock_response.action = 'ADVISE'
        mock_response.summary = 'Rude comment'
        mock_response.location = 'Unknown'
        
        mock_analyze.return_value = mock_response

        result = decision_engine.analyze_text("You are stupid")

        self.assertEqual(result.risk_score, 2)
        self.assertTrue(result.should_advise)


class ChatSessionTest(TestCase):
    def test_session_cancellation(self):
        """Test session cancellation logic"""
        session = ChatSession.objects.create(chat_id="12345")
        
        # Initially not cancelled
        self.assertFalse(session.is_cancelled())
        
        # Cancel it
        session.set_cancelled(seconds=3600)
        self.assertTrue(session.is_cancelled())
        
        # Clear it
        session.clear_cancelled()
        self.assertFalse(session.is_cancelled())
