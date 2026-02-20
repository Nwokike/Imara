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
        
        # Patch the agent's process method to return a valid bundle without calling LLM
        with patch('triage.agents.sentinel.SentinelAgent.process') as m_process:
            m_process.side_effect = lambda b: b
            decision_engine.process_incident("Harassment", metadata={"incident_id": incident.pk})
            
        incident.refresh_from_db()
        self.assertGreater(len(incident.reasoning_log), 0)
        self.assertEqual(incident.reasoning_log[0]["agent"], "Sentinel")

class ConversationEngineLogicTest(TestCase):
    """Test the logic and enforcement rules of the ConversationEngine."""
    
    def setUp(self):
        from triage.conversation_engine import ConversationEngine
        self.engine = ConversationEngine()

    def test_high_risk_requires_location(self):
        """High risk (7+) should force state to ASKING_LOCATION if location is missing."""
        payload = {
            "response": "I see the threat.",
            "state": "PROCESSING",
            "gathered_info": {
                "risk_score": 8,
                "user_confirmed": True
                # Missing location
            }
        }
        resp = self.engine._parse_llm_response(__import__("json").dumps(payload))
        self.assertEqual(resp.state, "ASKING_LOCATION")
        self.assertFalse(resp.should_create_report)

    def test_high_risk_requires_confirmation(self):
        """High risk (7+) should force state to CONFIRMING if not confirmed."""
        payload = {
            "response": "I see the threat.",
            "state": "PROCESSING",
            "gathered_info": {
                "risk_score": 8,
                "location": "Lagos, Nigeria",
                "user_confirmed": False
            }
        }
        resp = self.engine._parse_llm_response(__import__("json").dumps(payload))
        self.assertEqual(resp.state, "CONFIRMING")
        self.assertFalse(resp.should_create_report)

    def test_mandatory_fields_enforcement(self):
        """Regardless of risk, name and description are required for escalation."""
        payload = {
            "response": "I see the threat.",
            "state": "PROCESSING",
            "gathered_info": {
                "risk_score": 5,
                "location": "Accra, Ghana",
                "user_confirmed": True
                # Missing reporter_name, incident_description
            }
        }
        resp = self.engine._parse_llm_response(__import__("json").dumps(payload))
        self.assertEqual(resp.state, "GATHERING")
        self.assertIn("missing_fields", resp.gathered_info)

    def test_low_risk_allowed_directly(self):
        """Low risk (score < 7) can bypass location if logic allows (legacy support)."""
        payload = {
            "response": "Advice given.",
            "state": "LOW_RISK_ADVISE",
            "gathered_info": {"risk_score": 2}
        }
        resp = self.engine._parse_llm_response(__import__("json").dumps(payload))
        self.assertEqual(resp.state, "LOW_RISK_ADVISE")
        self.assertTrue(resp.is_low_risk)

from triage.clients.groq_client import GroqClient
from triage.clients.gemini_client import GeminiClient

class AIClientTest(TestCase):
    @patch('requests.post')
    def test_groq_text_analysis(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"risk_score": 8, "action": "REPORT", "summary": "Threat"}'}}]
        }
        mock_post.return_value = mock_response
        
        client = GroqClient()
        # Mock available
        client._available = True
        client.api_key = "test"
        
        result = client.analyze_text("I will find you")
        self.assertEqual(result.risk_score, 8)
        self.assertEqual(result.action, "REPORT")

    @patch('requests.post')
    def test_groq_transcription(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Help me please"
        mock_post.return_value = mock_response
        
        client = GroqClient()
        client._available = True
        client.api_key = "test"
        
        from io import BytesIO
        audio = BytesIO(b"fake-audio")
        text = client.transcribe_audio(audio)
        self.assertEqual(text, "Help me please")

    def test_gemini_vision_analysis(self):
        """Test Gemini vision analysis with mocked SDK."""
        client = GeminiClient()
        client._available = True
        client.client = MagicMock()
        
        # Mock the SDK response
        mock_res = MagicMock()
        mock_res.text = '{"risk_score": 9, "action": "REPORT", "summary": "Visual threat", "extracted_text": "I see you"}'
        client.client.models.generate_content.return_value = mock_res
        
        from io import BytesIO
        img = BytesIO(b"fake-img")
        result = client.analyze_image(img, "image/jpeg")
        self.assertEqual(result.risk_score, 9)
        self.assertEqual(result.extracted_text, "I see you")
