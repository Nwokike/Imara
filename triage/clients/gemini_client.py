import os
import json
import logging
import time
import threading
from typing import Optional
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')


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
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
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
        # Now supports ASK_LOCATION like Groq client
        if data['action'] not in ['ADVISE', 'REPORT', 'ASK_LOCATION']:
            data['action'] = 'ADVISE'
        
        return data
    
    def analyze_image(self, image_file_or_path, mime_type: Optional[str] = None) -> ImageAnalysis:
        if not self.is_available:
            return self._get_fallback_analysis()
        
        try:
            if isinstance(image_file_or_path, str):
                with open(image_file_or_path, 'rb') as f:
                    image_bytes = f.read()
                    if not mime_type:
                        mime_type = self._get_mime_type(image_file_or_path)
            else:
                f = image_file_or_path
                if hasattr(f, 'seek'):
                    f.seek(0)
                image_bytes = f.read()
                if not mime_type:
                    mime_type = "image/jpeg"
            
            return self.analyze_image_bytes(image_bytes, mime_type)
            
        except FileNotFoundError:
            raise GeminiClientError(f"Image file not found")
        except Exception as e:
            raise GeminiClientError(f"Failed to process image: {e}")

    def analyze_image_bytes(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ImageAnalysis:
        if not self.is_available:
            return self._get_fallback_analysis()
        
        from google.genai import types
        
        system_prompt = """You are Project Imara's Visual Guardian - an autonomous AI agent for OGBV threat verification.

MENTAL STATE:
Usage of this image is for SAFETY. You must extract text and context to determine if a woman is in danger.

AGENTIC DECISION MATRIX:
1. **NO VISIBLE THREAT**:
   - If image is blurry/irrelevant -> Risk: 1, Action: ADVISE ("Please upload a clearer screenshot").
   
2. **VISIBLE THREAT + UNKNOWN LOCATION**:
   - IF valid threat (stalking/doxing/rape/death threats/severe harassment) OR Risk Score >= 7 -> Action: ASK_LOCATION.
   - Note: We need location to dispatch help. If Risk is High, do NOT just Advise.

3. **VISIBLE THREAT + LOCATION FOUND**:
   - IF threats + location (e.g., address, city) -> Action: REPORT.
   
4. **HARASSMENT**:
   - Insults/Slurs -> Action: ADVISE (Block/Report to platform).

RULES:
- Extract ALL text into `extracted_text`.
- Detect "Sextortion" (threats to leak nudes).
- Detect "Doxing" (sharing private numbers/addresses).

You MUST respond with valid JSON only."""

        user_prompt = """Analyze this screenshot for threats related to online gender-based violence.

1. First, extract ALL visible text from the image
2. Then analyze the content for threats

Respond with this exact JSON structure:
{
    "risk_score": <1-10>,
    "action": "ADVISE" or "REPORT" or "ASK_LOCATION",
    "location": "<extracted location or 'Unknown'>",
    "summary": "<brief 1-sentence summary of the threat>",
    "advice": "<helpful advice if action is ADVISE, null otherwise>",
    "threat_type": "<type: insult/harassment/threat/doxing/blackmail/stalking/other>",
    "extracted_text": "<all text extracted from the image>"
}"""

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
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
            advice='Please review the content manually. If you feel threatened, contact local emergency services.',
            threat_type='unknown',
            extracted_text='[Text extraction unavailable - AI service not configured]'
        )


def get_gemini_client() -> GeminiClient:
    return GeminiClient()
