import os
import json
import logging
import requests
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class ThreatAnalysis(BaseModel):
    risk_score: int
    action: str
    location: Optional[str] = None
    summary: str
    advice: Optional[str] = None
    threat_type: Optional[str] = None


class GroqClient:
    def __init__(self):
        self.api_key = os.environ.get('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def analyze_text(self, text: str) -> ThreatAnalysis:
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
            response = requests.post(
                GROQ_API_URL,
                headers=self.headers,
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                    "response_format": {"type": "json_object"}
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            content = result['choices'][0]['message']['content']
            analysis_data = json.loads(content)
            
            return ThreatAnalysis(**analysis_data)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Groq response: {e}")
            raise
        except Exception as e:
            logger.error(f"Groq analysis failed: {e}")
            raise
    
    def transcribe_audio(self, audio_path: str) -> str:
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
                
        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            raise
