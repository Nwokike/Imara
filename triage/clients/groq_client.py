import os
import json
import logging
import time
import threading
import requests
from typing import Optional
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
WHISPER_MODEL = os.environ.get('WHISPER_MODEL', 'whisper-large-v3')
MAX_RETRIES = 3
RETRY_DELAY = 1


class ThreatAnalysis(BaseModel):
    risk_score: int
    action: str
    location: Optional[str] = None
    summary: str
    advice: Optional[str] = None
    threat_type: Optional[str] = None
    detected_language: Optional[str] = None


class GroqClientError(Exception):
    pass


class GroqClient:
    _instance = None
    _initialized = False
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if GroqClient._initialized:
            return
        
        self.api_key = os.environ.get('GROQ_API_KEY')
        self._available = bool(self.api_key)
        
        if self._available:
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        else:
            self.headers = {}
            logger.warning("GROQ_API_KEY not found - Groq client will use fallback responses")
        
        GroqClient._initialized = True
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def _make_request_with_retry(self, url: str, payload: dict, timeout: int = 30) -> dict:
        if not self._available:
            raise GroqClientError("Groq API key not configured")
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"Groq API timeout (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    last_error = e
                    logger.warning(f"Groq API rate limited (attempt {attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1) * 2)
                else:
                    raise GroqClientError(f"Groq API error: {e}")
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Groq API request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        
        raise GroqClientError(f"Groq API failed after {MAX_RETRIES} attempts: {last_error}")
    
    def analyze_text(self, text: str, conversation_context: list = None) -> ThreatAnalysis:
        if not self._available:
            return self._get_fallback_analysis(text)
        
        context_str = ""
        if conversation_context:
            context_str = "\n".join(conversation_context[-10:])
        
        system_prompt = """You are Project Imara's AI Sentinel - a specialized, autonomous agent designed to protect women and girls from online gender-based violence (OGBV).

MENTAL STATE & GOAL:
You are not just a classifier; you are a Guardian. Your goal is to ASSESS THREATS and PROTECT USERS.
You must determining if you have enough information to make a decision. If not, you must ASK for it.

AGENTIC STATES:
1. **STATE: INSUFFICIENT_DATA** -> ACTION: ASK_LOCATION or ASK_CONTEXT
   - If the user says "I am scared" or "Help me", you DO NOT know what is happening.
   - YOU MUST ASK: "Where are you? (City/Country)" or "What happened? Please describe the threat."
   - TRIGGER: Risk is high/unknown but Location/Context is missing.

2. **STATE: THREAT_DETECTED** -> ACTION: REPORT
   - If you have Evidence + Location + High Risk (7-10).
   - "He sent me death threats and I live in Lagos." -> REPORT.

3. **STATE: LOW_RISK** -> ACTION: ADVISE
   - Insults, rude behavior, general inquiries.

CLASSIFICATION RULES:
- risk_score: 1-3 (Low/Insult), 4-6 (Moderate/Harassment), 7-10 (Severe/Death Threats/Doxing)
- action: "ADVISE", "REPORT", "ASK_LOCATION", "ASK_CONTEXT"

LANGUAGE & TONE:
- Be empathetic but firm.
- Detect language (Pidgin, Swahili, etc.)
- African Context: Recognize locations like Lagos, Nairobi, Abuja, Port Harcourt.

OUTPUT FORMAT:
You MUST respond with valid JSON only."""

        user_prompt = f"""Analyze this message for threats against women/girls.

{"CONVERSATION HISTORY:" + chr(10) + context_str + chr(10) + chr(10) if context_str else ""}CURRENT MESSAGE: "{text}"

Respond with this exact JSON structure:
{{
    "risk_score": <1-10>,
    "action": "ADVISE" or "REPORT" or "ASK_LOCATION",
    "location": "<extracted location or 'Unknown'>",
    "summary": "<brief 1-sentence summary of the threat>",
    "advice": "<helpful advice if action is ADVISE, null otherwise>",
    "threat_type": "<type: insult/harassment/threat/doxing/blackmail/stalking/other>",
    "detected_language": "<language detected: english/pidgin/swahili/etc>"
}}"""

        try:
            result = self._make_request_with_retry(
                GROQ_API_URL,
                {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                    "response_format": {"type": "json_object"}
                }
            )
            
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not content:
                raise GroqClientError("Empty response from Groq API")
            
            try:
                analysis_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Groq response as JSON: {e}")
                raise GroqClientError(f"Invalid JSON response: {e}")
            
            if 'risk_score' not in analysis_data:
                analysis_data['risk_score'] = 5
            if 'action' not in analysis_data:
                analysis_data['action'] = 'ADVISE'
            if 'summary' not in analysis_data:
                analysis_data['summary'] = 'Content analyzed'
            
            analysis_data['risk_score'] = max(1, min(10, int(analysis_data.get('risk_score', 5))))
            analysis_data['action'] = analysis_data.get('action', 'ADVISE').upper()
            if analysis_data['action'] not in ['ADVISE', 'REPORT', 'ASK_LOCATION']:
                analysis_data['action'] = 'ADVISE'
            
            return ThreatAnalysis(**analysis_data)
            
        except GroqClientError:
            raise
        except ValidationError as e:
            logger.error(f"Response validation failed: {e}")
            raise GroqClientError(f"Response validation failed: {e}")
        except Exception as e:
            logger.error(f"Groq analysis failed: {e}")
            raise GroqClientError(f"Analysis failed: {e}")
    
    def transcribe_audio(self, audio_file_or_path) -> str:
        if not self._available:
            raise GroqClientError("Groq API key not configured for audio transcription")
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            f = None
            should_close = False
            try:
                if isinstance(audio_file_or_path, str):
                    f = open(audio_file_or_path, 'rb')
                    should_close = True
                    filename = os.path.basename(audio_file_or_path)
                else:
                    f = audio_file_or_path
                    if hasattr(f, 'seek'):
                        f.seek(0)
                    filename = getattr(f, 'name', 'audio.ogg')
                    if filename:
                        filename = os.path.basename(filename)
                    else:
                        filename = "audio.ogg"

                # Normalize extension for Groq/Whisper strict requirements
                supported_exts = ['flac', 'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'ogg', 'opus', 'wav', 'webm']
                name_parts = filename.rsplit('.', 1)
                ext = name_parts[1].lower() if len(name_parts) > 1 else ''
                
                if ext not in supported_exts:
                    if ext == 'oga': # Common Telegram voice note extension
                        filename = name_parts[0] + '.ogg'
                        mime_type = 'audio/ogg'
                    else:
                        # Fallback to .ogg if extension is unknown or missing
                        filename = (name_parts[0] if ext else filename) + '.ogg'
                        mime_type = 'audio/ogg'
                else:
                    # Map common mime types
                    mime_map = {
                        'mp3': 'audio/mpeg',
                        'wav': 'audio/wav',
                        'ogg': 'audio/ogg',
                        'm4a': 'audio/mp4',
                    }
                    mime_type = mime_map.get(ext, 'audio/mpeg')

                response = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (filename, f, mime_type)},
                    data={
                        "model": "whisper-large-v3",
                        "response_format": "text"
                    },
                    timeout=60
                )
                response.raise_for_status()
                return response.text.strip()
                    
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"Audio transcription timeout (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    
            except requests.exceptions.HTTPError as e:
                last_error = e
                try:
                    error_msg = response.json().get('error', {}).get('message', response.text)
                except:
                    error_msg = response.text
                logger.error(f"Groq API HTTP error: {error_msg}")
                if response.status_code != 429: # Don't retry non-429 HTTP errors unless it's a timeout
                    raise GroqClientError(f"Groq API error: {error_msg}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1) * 2)

            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Audio transcription failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
            except FileNotFoundError as e:
                raise GroqClientError(f"Audio file not found: {audio_file_or_path}")
            except Exception as e:
                logger.error(f"Audio transcription failed: {e}")
                raise GroqClientError(f"Audio transcription failed: {e}")
            finally:
                if should_close and f:
                    f.close()
        
        raise GroqClientError(f"Audio transcription failed after {MAX_RETRIES} attempts: {last_error}")
    
    def _get_fallback_analysis(self, text: str) -> ThreatAnalysis:
        text_lower = text.lower()
        
        high_risk_keywords = ['kill', 'murder', 'die', 'dead', 'address', 'where you live', 
                              'find you', 'revenge porn', 'nude', 'blackmail', 'stalk']
        moderate_keywords = ['hate', 'ugly', 'stupid', 'idiot', 'worthless', 'harassment']
        
        risk_score = 3
        action = 'ADVISE'
        threat_type = 'insult'
        
        for keyword in high_risk_keywords:
            if keyword in text_lower:
                risk_score = 8
                action = 'REPORT'
                threat_type = 'threat'
                break
        
        if risk_score < 7:
            for keyword in moderate_keywords:
                if keyword in text_lower:
                    risk_score = max(risk_score, 4)
                    threat_type = 'harassment'
        
        return ThreatAnalysis(
            risk_score=risk_score,
            action=action,
            location='Unknown',
            summary='Content analyzed using fallback system',
            advice='Block the sender and document any further incidents.' if action == 'ADVISE' else None,
            threat_type=threat_type
        )


def get_groq_client() -> GroqClient:
    return GroqClient()
