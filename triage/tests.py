from django.test import TestCase
from unittest.mock import patch, MagicMock
from .decision_engine import decision_engine, TriageResult

class DecisionEngineTest(TestCase):
    
    @patch('triage.clients.groq_client.GroqClient.analyze_text')
    def test_analyze_text_high_risk(self, mock_analyze):
        """Test that high risk text returns a REPORT action"""
        # Mock the return value of Groq
        mock_response = MagicMock()
        mock_response.risk_score = 9
        mock_response.action = 'REPORT'
        mock_response.summary = 'Death threat detected'
        mock_response.threat_type = 'threat'
        mock_response.location = 'Lagos'
        mock_response.advice = None
        
        mock_analyze.return_value = mock_response

        # Run the engine
        result = decision_engine.analyze_text("I will kill you")

        # Verify
        self.assertEqual(result.risk_score, 9)
        self.assertTrue(result.should_report)
        self.assertEqual(result.location, 'Lagos')

    @patch('triage.clients.groq_client.GroqClient.analyze_text')
    def test_analyze_text_low_risk(self, mock_analyze):
        """Test that low risk text returns an ADVISE action"""
        mock_response = MagicMock()
        mock_response.risk_score = 2
        mock_response.action = 'ADVISE'
        mock_response.summary = 'Rude comment'
        mock_response.threat_type = 'insult'
        
        mock_analyze.return_value = mock_response

        result = decision_engine.analyze_text("You are stupid")

        self.assertEqual(result.risk_score, 2)
        self.assertTrue(result.should_advise)
