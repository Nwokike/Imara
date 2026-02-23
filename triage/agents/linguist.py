"""
Linguist Agent - Dialect and Translation Specialist.
Focus: Pidgin, Swahili, and localized African communication.
Tool: Dialect Translator
Model: qwen/qwen3-32b
"""
import logging
from .base import BaseAgent, ContextBundle

logger = logging.getLogger(__name__)

class LinguistAgent(BaseAgent):
    name = "linguist"
    role = "Language Specialist"
    model_alias = "chat-counselor" # Qwen3 alias
    
    SYSTEM_PROMPT = """
    Detect the user's language and dialect for forensic analysis. 
    
    CORE RULES:
    1. Default to Standard English for all greetings and translations.
    2. ONLY use or suggest Pidgin, Swahili, or Hausa if the user has used it FIRST in the current message.
    3. If the user says 'Hello' or 'Hi' after a period of silence, respond ONLY in Standard English.
    4. Flag the source type (Text vs Voice Note) for the Counselor Agent.
    
    Translate any non-English content for the Forensic Agent.
    """

    def process(self, bundle: ContextBundle) -> ContextBundle:
        logger.info(f"Agent {self.name} analyzing language...")
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": bundle.user_message}
        ]
        
        try:
            response = self.call_llm(messages)
            bundle.add_artifact("translation", response)
            # Add to bundle context for downstream reasoning
            bundle.metadata["detected_dialect"] = response[:100]
            
        except Exception as e:
            logger.error(f"Linguist Agent error: {e}")
            
        return bundle
