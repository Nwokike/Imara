import os
import json
import logging
import time
from typing import Optional
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1


class ImageAnalysis(BaseModel):
    risk_score: int
    action: str
    location: Optional[str] = None
    summary: str
    advice: Optional[str] = None
    threat_type: Optional[str] = None
    extracted_text: Optional[str] = None


class GeminiClientError(Exception):
    pass


class GeminiClient:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if GeminiClient._initialized:
            return
        
        self.api_key = os.environ.get('GEMINI_API_KEY')
        self._available = bool(self.api_key)
        self.client = None
        
        if self._available:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self._available = False
        else:
            logger.warning("GEMINI_API_KEY not found - Gemini client will use fallback responses")
        
        GeminiClient._initialized = True
    
    @property
    def is_available(self) -> bool:
        return self._available and self.client is not None
    
    def _parse_response(self, content: str) -> dict:
        if not content:
            raise GeminiClientError("Empty response from Gemini")
        
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            raise GeminiClientError(f"Invalid JSON response: {e}")
    
    def _validate_and_normalize(self, data: dict) -> dict:
        if 'risk_score' not in data:
            data['risk_score'] = 5
        if 'action' not in data:
            data['action'] = 'ADVISE'
        if 'summary' not in data:
            data['summary'] = 'Image analyzed'
        
        data['risk_score'] = max(1, min(10, int(data.get('risk_score', 5))))
        data['action'] = str(data.get('action', 'ADVISE')).upper()
        if data['action'] not in ['ADVISE', 'REPORT']:
            data['action'] = 'ADVISE'
        
        return data
    
    def analyze_image(self, image_path: str) -> ImageAnalysis:
        if not self.is_available:
            return self._get_fallback_analysis()
        
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
        except FileNotFoundError:
            raise GeminiClientError(f"Image file not found: {image_path}")
        except Exception as e:
            raise GeminiClientError(f"Failed to read image file: {e}")
        
        mime_type = self._get_mime_type(image_path)
        return self.analyze_image_bytes(image_bytes, mime_type)
    
    def analyze_image_bytes(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ImageAnalysis:
        if not self.is_available:
            return self._get_fallback_analysis()
        
        from google.genai import types
        
        system_prompt = """You are Project Imara's Visual Analysis System - a specialized OCR and threat assessment engine designed to protect women and girls from online gender-based violence (OGBV).

Your role is to:
1. Extract ALL text visible in the screenshot/image using OCR
2. Analyze the extracted content for threats
3. Determine the appropriate response

CLASSIFICATION RULES:
- risk_score: 1-10 scale (1-3: low/insults, 4-6: moderate/harassment, 7-10: severe/threats/doxing)
- action: "ADVISE" for low-moderate risk OR "REPORT" for high risk (escalate to authorities)

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

IMPORTANT: Include ALL extracted text in the extracted_text field.

You MUST respond with valid JSON only."""

        user_prompt = """Analyze this screenshot for threats against women/girls.

1. First, extract ALL visible text from the image
2. Then analyze the content for threats

Respond with this exact JSON structure:
{
    "risk_score": <1-10>,
    "action": "ADVISE" or "REPORT",
    "location": "<extracted location or 'Unknown'>",
    "summary": "<brief 1-sentence summary of the threat>",
    "advice": "<helpful advice if action is ADVISE, null if REPORT>",
    "threat_type": "<type: insult/harassment/threat/doxing/blackmail/stalking/other>",
    "extracted_text": "<all text extracted from the image>"
}"""

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                                types.Part(text=f"{system_prompt}\n\n{user_prompt}")
                            ]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    )
                )
                
                analysis_data = self._parse_response(response.text)
                analysis_data = self._validate_and_normalize(analysis_data)
                
                return ImageAnalysis(**analysis_data)
                
            except GeminiClientError:
                raise
            except ValidationError as e:
                logger.error(f"Response validation failed: {e}")
                raise GeminiClientError(f"Response validation failed: {e}")
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        
        logger.error(f"Gemini analysis failed after {MAX_RETRIES} attempts: {last_error}")
        raise GeminiClientError(f"Analysis failed after {MAX_RETRIES} attempts: {last_error}")
    
    def _get_mime_type(self, file_path: str) -> str:
        extension = file_path.lower().split('.')[-1]
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
        }
        return mime_types.get(extension, 'image/jpeg')
    
    def _get_fallback_analysis(self) -> ImageAnalysis:
        return ImageAnalysis(
            risk_score=5,
            action='ADVISE',
            location='Unknown',
            summary='Image analyzed using fallback system - AI service unavailable',
            advice='Please review the content manually. If you feel threatened, contact local authorities.',
            threat_type='unknown',
            extracted_text='[Text extraction unavailable - AI service not configured]'
        )


def get_gemini_client() -> GeminiClient:
    return GeminiClient()
