"""
Visionary Agent - Multi-modal Evidence Specialist.
Focus: OCR and visual threat detection from screenshots.
Tool: Image Analyzer
Model: llama-4-maverick-17b (Native Multimodal)
"""
import logging
import json
from .base import BaseAgent, ContextBundle

logger = logging.getLogger(__name__)

class VisionaryAgent(BaseAgent):
    name = "visionary"
    role = "Evidence Analyst"
    model_alias = "vision-specialist"
    
    SYSTEM_PROMPT = """
    Extract all text from the provided screenshot. 
    Identify any visible threats, doxing, or harassment in the image.
    
    RESPOND IN JSON FORMAT ONLY:
    {
        "extracted_text": "<text>",
        "visual_threats": ["threat1", "threat2"],
        "confidence": <0.0-1.0>
    }
    """

    def process(self, bundle: ContextBundle) -> ContextBundle:
        logger.info(f"Agent {self.name} analyzing image evidence...")
        
        image_url = bundle.metadata.get("image_url")
        if not image_url:
            bundle.add_artifact("vision_analysis", {"error": "No image URL provided"})
            return bundle
            
        # In 2026, we use LiteLLM to pass the URL directly if supported by Maverick/Gemini
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self.SYSTEM_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
        
        try:
            response_text = self.call_llm(messages, response_format={"type": "json_object"})
            result = json.loads(response_text)
            
            bundle.add_artifact("vision_analysis", result)
            bundle.user_message += f"\n[Vision Summary]: {result.get('extracted_text')}"
            
        except Exception as e:
            logger.error(f"Visionary Agent error: {e}")
            
        return bundle
