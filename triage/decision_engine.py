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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "action": self.action,
            "location": self.location,
            "summary": self.summary,
            "advice": self.advice,
            "threat_type": self.threat_type,
            "extracted_text": self.extracted_text,
            "source_type": self.source_type
        }
    
    @property
    def should_report(self) -> bool:
        return self.action.upper() == "REPORT"
    
    @property
    def should_advise(self) -> bool:
        return self.action.upper() == "ADVISE"


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
    
    def analyze_text(self, text: str) -> TriageResult:
        try:
            analysis = self.groq_client.analyze_text(text)
            
            return TriageResult(
                risk_score=analysis.risk_score,
                action=analysis.action,
                location=analysis.location,
                summary=analysis.summary,
                advice=analysis.advice,
                threat_type=analysis.threat_type,
                source_type="text"
            )
        except GroqClientError as e:
            logger.error(f"Groq client error: {e}")
            return self._get_fallback_result("text", str(e))
        except Exception as e:
            logger.error(f"Text analysis failed: {e}")
            return self._get_fallback_result("text", str(e))
    
    def analyze_image(self, image_path: str) -> TriageResult:
        try:
            analysis = self.gemini_client.analyze_image(image_path)
            
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
    
    def analyze_audio(self, audio_path: str) -> TriageResult:
        try:
            transcribed_text = self.groq_client.transcribe_audio(audio_path)
            
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
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        audio_path: Optional[str] = None,
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
    
    def _get_fallback_result(self, source_type: str, error_message: str) -> TriageResult:
        return TriageResult(
            risk_score=5,
            action="ADVISE",
            location="Unknown",
            summary="Unable to fully analyze the content due to a technical issue",
            advice="If you feel threatened, please contact local authorities directly. You can also try submitting again.",
            threat_type="unknown",
            source_type=source_type,
            error=error_message
        )


decision_engine = DecisionEngine()
