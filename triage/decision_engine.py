import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .agents.base import ContextBundle
from .agents.sentinel import SentinelAgent
from .agents.visionary import VisionaryAgent
from .agents.navigator import NavigatorAgent
from .agents.forensic import ForensicAgent
from .agents.counselor import CounselorAgent

logger = logging.getLogger(__name__)

@dataclass
class TriageResult:
    risk_score: int
    action: str
    location: Optional[str]
    summary: str
    advice: Optional[str]
    threat_type: Optional[str]
    extracted_text: Optional[str] = None
    source_type: str = "text"
    error: Optional[str] = None
    forensic_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "action": self.action,
            "location": self.location,
            "summary": self.summary,
            "advice": self.advice,
            "threat_type": self.threat_type,
            "extracted_text": self.extracted_text,
            "source_type": self.source_type,
            "forensic_hash": self.forensic_hash
        }
    
    @property
    def should_report(self) -> bool:
        return self.action.upper() == "REPORT"
    
    @property
    def needs_location(self) -> bool:
        return self.action.upper() == "ASK_LOCATION"

class DecisionEngine:
    """
    Imara's Agent Orchestrator.
    Manages the 7-agent 'Bodyguard Hive' pipeline.
    """
    
    def __init__(self):
        self._sentinel = None
        self._linguist = None
        self._visionary = None
        self._navigator = None
        self._forensic = None
        self._counselor = None
        self._messenger = None

    @property
    def sentinel(self):
        if not self._sentinel: self._sentinel = SentinelAgent()
        return self._sentinel

    @property
    def linguist(self):
        if not self._linguist: self._linguist = LinguistAgent()
        return self._linguist

    @property
    def visionary(self):
        if not self._visionary: self._visionary = VisionaryAgent()
        return self._visionary

    @property
    def navigator(self):
        if not self._navigator: self._navigator = NavigatorAgent()
        return self._navigator

    @property
    def forensic(self):
        if not self._forensic: self._forensic = ForensicAgent()
        return self._forensic

    @property
    def counselor(self):
        if not self._counselor: self._counselor = CounselorAgent()
        return self._counselor

    @property
    def messenger(self):
        if not self._messenger: self._messenger = MessengerAgent()
        return self._messenger

    def analyze_text(self, text: str, history: List[Dict[str, str]] = None) -> TriageResult:
        """Entry point for text analysis via orchestrator."""
        return self.process_incident(text, history=history)

    def analyze_image(self, image_file_or_path: Any) -> TriageResult:
        """Entry point for image analysis."""
        # For 1GB RAM, we pass the path/file to the visionary agent
        # The visionary agent uses LiteLLM which handles URLs or local paths
        return self.process_incident("Analyzing image...", image_url=str(image_file_or_path))

    def analyze_audio(self, audio_file: Any) -> TriageResult:
        """Entry point for audio transcription and analysis."""
        try:
            # For now, we still use the old GroqClient for transcription 
            # until the TranscriberAgent is fully standalone
            from .clients.groq_client import get_groq_client
            client = get_groq_client()
            text = client.transcribe_audio(audio_file)
            return self.process_incident(f"[Transcribed Audio]: {text}")
        except Exception as e:
            return self._get_fallback_triage(str(e))

    def chat_orchestration(
        self, 
        text: str, 
        history: List[Dict[str, str]],
        image_url: str = None,
        metadata: Dict[str, Any] = None
    ) -> TriageResult:
        """
        Orchestration for stateful chat platforms (Telegram, Meta, Discord).
        Includes full conversational history and empathetic reasoning.
        """
        return self.process_incident(
            text, 
            history=history, 
            image_url=image_url, 
            metadata={**(metadata or {}), "pipeline": "chat"}
        )

    def web_orchestration(
        self, 
        text: str, 
        image_url: str = None,
        metadata: Dict[str, Any] = None
    ) -> TriageResult:
        """
        Orchestration for stateless web forms.
        Focuses on immediate high-speed forensic analysis and reporting.
        """
        return self.process_incident(
            text, 
            history=[], # Stateless
            image_url=image_url, 
            metadata={**(metadata or {}), "pipeline": "web"}
        )

    def process_incident(
        self, 
        text: str, 
        history: List[Dict[str, str]] = None,
        image_url: str = None,
        metadata: Dict[str, Any] = None
    ) -> TriageResult:
        """
        Orchestrates the agent pipeline.
        """
        bundle = ContextBundle(
            user_message=text,
            conversation_history=history or [],
            metadata={**(metadata or {}), "image_url": image_url}
        )

        try:
            # 1. Safety Sentinel
            bundle = self.sentinel.process(bundle)
            
            # 2. Linguist (Dialect & Tone)
            bundle = self.linguist.process(bundle)
            
            # 3. Visionary (If evidence is visual)
            if image_url: bundle = self.visionary.process(bundle)
            
            # 4. Navigator (Jurisdiction)
            bundle = self.navigator.process(bundle)
            
            # 5. Forensic Reasoning
            bundle = self.forensic.process(bundle)
            
            # 6. Messenger Agent (Partner Dispatch Draft)
            bundle = self.messenger.process(bundle)
            
            # 7. Counselor (User-facing response)
            bundle = self.counselor.process(bundle)
            
            return self._bundle_to_result(bundle)

        except Exception as e:
            logger.error(f"Orchestration Hive failed: {e}")
            return self._get_fallback_triage(str(e))

    def _bundle_to_result(self, bundle: ContextBundle) -> TriageResult:
        safety = bundle.artifacts.get("safety_check", {})
        location = bundle.artifacts.get("location_analysis", {})
        forensic = bundle.artifacts.get("forensic_audit", {})
        
        return TriageResult(
            risk_score=forensic.get("urgency_rating", safety.get("risk_score", 5)),
            action=forensic.get("recommendation", "ADVISE").upper(),
            location=location.get("normalized_country", "Unknown"),
            summary=forensic.get("forensic_summary", safety.get("reasoning", "Analysis complete")),
            advice=bundle.artifacts.get("agent_response", "Please stay safe."),
            threat_type=forensic.get("legal_category", "unclassified"),
            extracted_text=bundle.artifacts.get("vision_analysis", {}).get("extracted_text"),
            forensic_hash=bundle.artifacts.get("forensic_hash")
        )

    def _get_fallback_triage(self, error: str) -> TriageResult:
        return TriageResult(
            risk_score=5,
            action="ADVISE",
            location="Unknown",
            summary="Technical reasoning error",
            advice="I'm having trouble with my advanced logic. Please contact emergency services if you are in danger.",
            threat_type="error",
            error=error
        )


# Singleton instance
decision_engine = DecisionEngine()
