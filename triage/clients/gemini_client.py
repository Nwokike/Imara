import os
import json
import logging
import base64
from typing import Optional
from pydantic import BaseModel

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class ImageAnalysis(BaseModel):
    risk_score: int
    action: str
    location: Optional[str] = None
    summary: str
    advice: Optional[str] = None
    threat_type: Optional[str] = None
    extracted_text: Optional[str] = None


class GeminiClient:
    def __init__(self):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=api_key)
    
    def analyze_image(self, image_path: str) -> ImageAnalysis:
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

        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            mime_type = self._get_mime_type(image_path)
            
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
            
            content = response.text
            if content:
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()
                
                analysis_data = json.loads(content)
                return ImageAnalysis(**analysis_data)
            else:
                raise ValueError("Empty response from Gemini")
                
        except Exception as e:
            logger.error(f"Gemini image analysis failed: {e}")
            raise
    
    def analyze_image_bytes(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ImageAnalysis:
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

ADVISE ONLY (action: "ADVISE", risk_score 1-6):
- General insults or name-calling
- Rude comments
- Mild harassment

You MUST respond with valid JSON only."""

        user_prompt = """Analyze this screenshot for threats against women/girls.

Respond with this exact JSON structure:
{
    "risk_score": <1-10>,
    "action": "ADVISE" or "REPORT",
    "location": "<extracted location or 'Unknown'>",
    "summary": "<brief summary>",
    "advice": "<advice if ADVISE, null if REPORT>",
    "threat_type": "<type>",
    "extracted_text": "<all text from image>"
}"""

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
            
            content = response.text
            if content:
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()
                
                analysis_data = json.loads(content)
                return ImageAnalysis(**analysis_data)
            else:
                raise ValueError("Empty response from Gemini")
                
        except Exception as e:
            logger.error(f"Gemini image analysis failed: {e}")
            raise
    
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
