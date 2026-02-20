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
    Detect the user's language and dialect. 
    RULE: Default to standard English for all analysis and translations. 
    ONLY suggest a non-English dialect (Pidgin, Swahili, Hausa) if the user has used it first in the current message.
    
    If it is Pidgin, Swahili, or Hausa, provide a clear English translation for the Forensic Agent.
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
