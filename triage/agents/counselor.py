"""
Counselor Agent - Empathetic Support.
Focus: Safety advice, de-escalation, and supportive dialogue.
Tool: Safety Advisor
Model: chat-counselor (Qwen / Kimi)
"""
import logging
from .base import BaseAgent, ContextBundle

logger = logging.getLogger(__name__)

class CounselorAgent(BaseAgent):
    name = "counselor"
    role = "Supportive Sister"
    model_alias = "chat-counselor"
    
    SYSTEM_PROMPT = """
    You are Imara, a compassionate protector for African women.
    Your tone is warm, patient, and firm on safety.
    
    MISSION:
    1. Acknowledge the victim's pain with deep empathy.
    2. Provide actionable safety advice (blocking, documenting, safe locations).
    3. Match their language (English, Pidgin, Swahili).
    
    If the risk is high, remind them they are not alone.
    """

    def process(self, bundle: ContextBundle) -> ContextBundle:
        logger.info(f"Agent {self.name} drafting response...")
        
        # Hydrate context with previous artifacts
        safety = bundle.artifacts.get("safety_check", {})
        location = bundle.artifacts.get("location_analysis", {})
        
        context_hint = f"Risk Level: {safety.get('risk_level', 'Unknown')}. Location: {location.get('normalized_country', 'Unknown')}."
        
        messages = [
            {"role": "system", "content": f"{self.SYSTEM_PROMPT}\nContext: {context_hint}"},
        ] + bundle.conversation_history[-10:] + [{"role": "user", "content": bundle.user_message}]
        
        try:
            response = self.call_llm(messages)
            bundle.add_artifact("agent_response", response)
            bundle.workflow_state = "READY_TO_REPLY"
            
        except Exception as e:
            logger.error(f"Counselor Agent error: {e}")
            bundle.add_artifact("agent_response", "I'm here for you. Please tell me more about what's happening so I can help.")
            
        return bundle
