from django.test import TestCase
from unittest.mock import MagicMock, patch
from .models import ChatSession, ChatMessage, UserFeedback
from .decision_engine import DecisionEngine, TriageResult
from .agents.base import ContextBundle
from .agents.sentinel import SentinelAgent
from .agents.linguist import LinguistAgent
from .agents.navigator import NavigatorAgent
from .agents.forensic import ForensicAgent
from .agents.counselor import CounselorAgent
from .agents.messenger import MessengerAgent

class AgentUnitTest(TestCase):
    """Unit tests for the individual micro-agents in the Hive."""
    
    def setUp(self):
        self.bundle = ContextBundle(user_message="I am being followed", conversation_history=[])

    @patch('triage.agents.base.BaseAgent.call_llm')
    def test_sentinel_agent(self, mock_call):
        mock_call.return_value = '{"is_safe": false, "risk_level": "high", "policy_violation": "stalking", "reasoning": "User followed"}'
        agent = SentinelAgent()
        result_bundle = agent.process(self.bundle)
        
        self.assertEqual(result_bundle.workflow_state, "THREAT_DETECTED")
        self.assertIn("safety_check", result_bundle.artifacts)
        self.assertEqual(result_bundle.artifacts["safety_check"]["risk_level"], "high")

    @patch('triage.agents.base.BaseAgent.call_llm')
    def test_linguist_agent(self, mock_call):
        mock_call.return_value = "This is a translation"
        agent = LinguistAgent()
        result_bundle = agent.process(self.bundle)
        
        self.assertIn("translation", result_bundle.artifacts)
        self.assertEqual(result_bundle.metadata["detected_dialect"], "This is a translation")

    @patch('triage.agents.base.BaseAgent.call_llm')
    def test_navigator_agent(self, mock_call):
        mock_call.return_value = '{"location": "Nairobi, Kenya", "confidence": 0.9, "is_africa": true, "needs_ask": false}'
        agent = NavigatorAgent()
        result_bundle = agent.process(self.bundle)
        
        self.assertIn("location_analysis", result_bundle.artifacts)
        self.assertEqual(result_bundle.artifacts["location_analysis"]["normalized_country"], "Kenya")

class DecisionEngineIntegrationTest(TestCase):
    """Integration tests for the Orchestrator Hive."""
    
    def setUp(self):
        self.engine = DecisionEngine()

    @patch('triage.decision_engine.DecisionEngine.sentinel', new_callable=MagicMock)
    @patch('triage.decision_engine.DecisionEngine.linguist', new_callable=MagicMock)
    @patch('triage.decision_engine.DecisionEngine.navigator', new_callable=MagicMock)
    @patch('triage.decision_engine.DecisionEngine.forensic', new_callable=MagicMock)
    @patch('triage.decision_engine.DecisionEngine.messenger', new_callable=MagicMock)
    @patch('triage.decision_engine.DecisionEngine.counselor', new_callable=MagicMock)
    def test_orchestration_pipeline(self, m_counselor, m_messenger, m_forensic, m_navigator, m_linguist, m_sentinel):
        # Setup mocks to return bundles with specific artifacts
        def mock_process(bundle):
            if "safety_check" not in bundle.artifacts:
                bundle.add_artifact("safety_check", {"risk_score": 8})
            elif "location_analysis" not in bundle.artifacts:
                bundle.add_artifact("location_analysis", {"normalized_country": "Nigeria"})
            elif "forensic_audit" not in bundle.artifacts:
                bundle.add_artifact("forensic_audit", {"recommendation": "report", "urgency_rating": 9, "forensic_summary": "Serious"})
            elif "agent_response" not in bundle.artifacts:
                bundle.add_artifact("agent_response", "Stay safe")
            return bundle

        m_sentinel.process.side_effect = mock_process
        m_linguist.process.side_effect = lambda b: b
        m_navigator.process.side_effect = mock_process
        m_forensic.process.side_effect = mock_process
        m_messenger.process.side_effect = lambda b: b
        m_counselor.process.side_effect = mock_process

        result = self.engine.process_incident("Help me")
        
        self.assertEqual(result.risk_score, 9)
        self.assertEqual(result.action, "REPORT")
        self.assertEqual(result.location, "Nigeria")
        self.assertEqual(result.advice, "Stay safe")

class TriageModelsTest(TestCase):
    def test_session_creation(self):
        session = ChatSession.objects.create(chat_id="12345", platform="telegram", username="testuser")
        self.assertEqual(session.chat_id, "12345")
        self.assertFalse(session.is_cancelled())

    def test_interaction_age(self):
        session = ChatSession.objects.create(chat_id="interaction_test")
        # No messages yet
        self.assertEqual(session.get_last_interaction_age(), float('inf'))
        
        ChatMessage.objects.create(session=session, role="user", content="Hi")
        age = session.get_last_interaction_age()
        self.assertLess(age, 5)

class HiveReasoningTest(TestCase):
    """Test the streaming reasoning trail features."""
    
    def test_reasoning_log_streaming(self):
        from cases.models import IncidentReport
        from .decision_engine import decision_engine
        
        incident = IncidentReport.objects.create(source='web', original_text="Harassment")
        
        # We manually trigger orchestration with mocks to check log population
        # (This is a sanity check for the logging callback)
        with patch.object(DecisionEngine, 'sentinel') as m_sentinel:
            m_sentinel.process.return_value = ContextBundle("Harassment", [])
            decision_engine.process_incident("Harassment", metadata={"incident_id": incident.pk})
            
        incident.refresh_from_db()
        self.assertGreater(len(incident.reasoning_log), 0)
        self.assertEqual(incident.reasoning_log[0]["agent"], "Sentinel")
