import os
import json
import logging
import time
import requests
from typing import Optional
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_RETRIES = 3
RETRY_DELAY = 1


class ThreatAnalysis(BaseModel):
    risk_score: int
    action: str
    location: Optional[str] = None
    summary: str
    advice: Optional[str] = None
    threat_type: Optional[str] = None


class GroqClientError(Exception):
    pass


class GroqClient:
    _instance = None
    _initialized = False
    
    def __new__(cls):
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
    
    def analyze_text(self, text: str) -> ThreatAnalysis:
        if not self._available:
            return self._get_fallback_analysis(text)
        
        system_prompt = """You are Project Imara's AI Triage System - a specialized threat assessment engine designed to protect women and girls from online gender-based violence (OGBV).

Your role is to analyze messages/content and determine the appropriate response.

CLASSIFICATION RULES:
- risk_score: 1-10 scale (1-3: low/insults, 4-6: moderate/harassment, 7-10: severe/threats/doxing)
- action: "ADVISE" for low-moderate risk (give advice) OR "REPORT" for high risk (escalate to authorities)

ALWAYS REPORT (action: "REPORT", risk_score 7-10):
- Death threats or threats of physical violence
- Doxing (sharing private information like address, phone, workplace)
- Blackmail or extortion
- Sexual assault threats
- Stalking behavior
- Revenge porn threats
- Threats to family members

ADVISE ONLY (action: "ADVISE", risk_score 1-6):
- General insults or name-calling
- Rude comments
- Mild harassment
- Offensive language without threats

LOCATION EXTRACTION:
- Extract any location mentioned (city, state, country)
- Default to "Unknown" if no location found

You MUST respond with valid JSON only, no other text."""

        user_prompt = f"""Analyze this message for threats against women/girls:

MESSAGE: "{text}"

Respond with this exact JSON structure:
{{
    "risk_score": <1-10>,
    "action": "ADVISE" or "REPORT",
    "location": "<extracted location or 'Unknown'>",
    "summary": "<brief 1-sentence summary of the threat>",
    "advice": "<helpful advice if action is ADVISE, null if REPORT>",
    "threat_type": "<type: insult/harassment/threat/doxing/blackmail/stalking/other>"
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
            if analysis_data['action'] not in ['ADVISE', 'REPORT']:
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
    
    def transcribe_audio(self, audio_path: str) -> str:
        if not self._available:
            raise GroqClientError("Groq API key not configured for audio transcription")
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                with open(audio_path, 'rb') as audio_file:
                    response = requests.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": audio_file},
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
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Audio transcription failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
            except FileNotFoundError as e:
                raise GroqClientError(f"Audio file not found: {audio_path}")
            except Exception as e:
                logger.error(f"Audio transcription failed: {e}")
                raise GroqClientError(f"Audio transcription failed: {e}")
        
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
