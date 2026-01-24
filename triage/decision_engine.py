import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .clients import get_groq_client, get_gemini_client, GroqClientError, GeminiClientError

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
    detected_language: Optional[str] = None
    
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
            "detected_language": self.detected_language
        }
    
    @property
    def should_report(self) -> bool:
        return self.action.upper() == "REPORT"
    
    @property
    def should_advise(self) -> bool:
        return self.action.upper() == "ADVISE"
    
    @property
    def needs_location(self) -> bool:
        return self.action.upper() == "ASK_LOCATION"


class DecisionEngine:
    def __init__(self):
        self._groq_client = None
        self._gemini_client = None
    
    @property
    def groq_client(self):
        if self._groq_client is None:
            self._groq_client = get_groq_client()
        return self._groq_client
    
    @property
    def gemini_client(self):
        if self._gemini_client is None:
            self._gemini_client = get_gemini_client()
        return self._gemini_client
    
    def analyze_text(self, text: str, conversation_context: list = None) -> TriageResult:
        try:
            analysis = self.groq_client.analyze_text(text, conversation_context)
            
            # SAFETY OVERRIDE: High Risk + Unknown Location = ASK_LOCATION
            if analysis.risk_score >= 7 and (not analysis.location or analysis.location.lower() in ['unknown', 'none', 'null', '']):
                analysis.action = 'ASK_LOCATION'
            
            return TriageResult(
                risk_score=analysis.risk_score,
                action=analysis.action,
                location=analysis.location,
                summary=analysis.summary,
                advice=analysis.advice,
                threat_type=analysis.threat_type,
                source_type="text",
                detected_language=getattr(analysis, 'detected_language', None)
            )
        except GroqClientError as e:
            logger.error(f"Groq client error: {e}")
            return self._get_fallback_result("text", str(e))
        except Exception as e:
            logger.error(f"Text analysis failed: {e}")
            return self._get_fallback_result("text", str(e))
    
    def analyze_image(self, image_file_or_path: Any) -> TriageResult:
        try:
            analysis = self.gemini_client.analyze_image(image_file_or_path)
            
            return TriageResult(
                risk_score=analysis.risk_score,
                action=analysis.action,
                location=analysis.location,
                summary=analysis.summary,
                advice=analysis.advice,
                threat_type=analysis.threat_type,
                extracted_text=analysis.extracted_text,
                source_type="image"
            )
        except GeminiClientError as e:
            logger.error(f"Gemini client error: {e}")
            return self._get_fallback_result("image", str(e))
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return self._get_fallback_result("image", str(e))
    
    def analyze_image_bytes(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> TriageResult:
        try:
            analysis = self.gemini_client.analyze_image_bytes(image_bytes, mime_type)
            
            # SAFETY OVERRIDE: High Risk + Unknown Location = ASK_LOCATION
            # This prevents dangerous "Reporting to Default" or "Just Advising" on severe threats
            if analysis.risk_score >= 7 and (not analysis.location or analysis.location.lower() in ['unknown', 'none', 'null', '']):
                analysis.action = 'ASK_LOCATION'
            
            return TriageResult(
                risk_score=analysis.risk_score,
                action=analysis.action,
                location=analysis.location,
                summary=analysis.summary,
                advice=analysis.advice,
                threat_type=analysis.threat_type,
                extracted_text=analysis.extracted_text,
                source_type="image"
            )
        except GeminiClientError as e:
            logger.error(f"Gemini client error: {e}")
            return self._get_fallback_result("image", str(e))
        except Exception as e:
            logger.error(f"Image bytes analysis failed: {e}")
            return self._get_fallback_result("image", str(e))
    
    def analyze_audio(self, audio_file_or_path: Any) -> TriageResult:
        try:
            transcribed_text = self.groq_client.transcribe_audio(audio_file_or_path)
            
            if not transcribed_text:
                return TriageResult(
                    risk_score=1,
                    action="ADVISE",
                    location="Unknown",
                    summary="No speech detected in the audio",
                    advice="Please submit a clearer audio recording if needed.",
                    threat_type="none",
                    extracted_text="",
                    source_type="audio"
                )
            
            result = self.analyze_text(transcribed_text)
            return TriageResult(
                risk_score=result.risk_score,
                action=result.action,
                location=result.location,
                summary=result.summary,
                advice=result.advice,
                threat_type=result.threat_type,
                extracted_text=transcribed_text,
                source_type="audio"
            )
            
        except GroqClientError as e:
            logger.error(f"Audio transcription error: {e}")
            return self._get_fallback_result("audio", str(e))
        except Exception as e:
            logger.error(f"Audio analysis failed: {e}")
            return self._get_fallback_result("audio", str(e))
    
    def process_evidence(
        self,
        text: Optional[str] = None,
        image_path: Optional[Any] = None,
        image_bytes: Optional[bytes] = None,
        audio_path: Optional[Any] = None,
        mime_type: str = "image/jpeg"
    ) -> TriageResult:
        if image_bytes:
            return self.analyze_image_bytes(image_bytes, mime_type)
        elif image_path:
            return self.analyze_image(image_path)
        elif audio_path:
            return self.analyze_audio(audio_path)
        elif text:
            return self.analyze_text(text)
        else:
            return TriageResult(
                risk_score=1,
                action="ADVISE",
                location="Unknown",
                summary="No evidence provided for analysis",
                advice="Please provide a message, screenshot, or voice note to analyze.",
                threat_type="none",
                source_type="unknown",
                error="No evidence provided"
            )

    # === Required field checks (partner action reliability) ===

    REQUIRED_FIELDS = ["reporter_name", "incident_description", "contact_preference"]
    HIGH_RISK_REQUIRED_FIELDS = ["location"]

    def check_required_fields(self, session, gathered_info: Optional[Dict[str, Any]] = None) -> list[str]:
        """
        Returns a list of missing fields required before creating/escalating a case.
        """
        info = gathered_info or {}
        missing: list[str] = []

        for f in self.REQUIRED_FIELDS:
            val = (info.get(f) or "").strip() if isinstance(info.get(f), str) else info.get(f)
            if not val:
                missing.append(f)

        # START NEW: Email validation
        contact_pref = (info.get('contact_preference') or "").lower()
        if "email" in contact_pref:
            email = (info.get('reporter_email') or "").strip()
            if not email:
                missing.append("reporter_email")
        # END NEW

        risk_score = info.get("risk_score") or 0
        if risk_score >= 7:
            for f in self.HIGH_RISK_REQUIRED_FIELDS:
                val = (info.get(f) or "").strip() if isinstance(info.get(f), str) else info.get(f)
                if not val or val == "Unknown":
                    missing.append(f)

        return missing

    def is_ready_for_case_creation(self, session, triage_result: Optional["TriageResult"] = None, gathered_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Returns True if we have enough information to create a case reliably.
        """
        info = gathered_info or {}
        missing = self.check_required_fields(session, info)
        if missing:
            return False
        # If triage_result exists and asks for location, we're not ready.
        if triage_result is not None and getattr(triage_result, "needs_location", False):
            return False
        return True
    
    def _get_fallback_result(self, source_type: str, error_message: str) -> TriageResult:
        return TriageResult(
            risk_score=5,
            action="ADVISE",
            location="Unknown",
            summary="Unable to fully analyze the content due to a technical issue",
            advice="If you feel threatened, please contact local emergency services directly. You can also try submitting again.",
            threat_type="unknown",
            source_type=source_type,
            error=error_message
        )


decision_engine = DecisionEngine()
