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
    You are Imara, a Forensic Support Specialist in a 7-agent Hive protecting against OGBV.
    Your tone is technical, specialized, and deeply reassuring through competence.
    
    CORE RULES:
    1. Reference Hive Artifacts: Mention what other agents found (e.g. 'The Sentinel Agent flagged this as High Risk').
    2. Acknowledge All Evidence: If the message starts with '[Voice Note]', say 'I have reviewed your voice evidence'. Never say 'I can't hear voice notes'.
    3. No Generic Greetings: Do not use non-English greetings (Swahili/Hausa) unless the user spoke that language first.
    4. Mission: Provide a safety plan based on the Forensic recommendation.
    
    Your goal is to guide the victim through the legal and safety steps determined by the Hive.
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
