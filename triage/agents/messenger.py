"""
Messenger Agent - Partner Dispatch Specialist.
Focus: Drafting and routing forensic alerts to partners.
Tool: Brevo Email
Model: kimi-k2-instruct
"""
import logging
import json
from .base import BaseAgent, ContextBundle

logger = logging.getLogger(__name__)

class MessengerAgent(BaseAgent):
    name = "messenger"
    role = "Dispatch Specialist"
    model_alias = "chat-fallback-1" # Kimi-K2
    
    SYSTEM_PROMPT = """
    Based on the forensic audit and victim context, draft a concise alert message
    for our support partners (NGOs/Police). Focus on urgency and evidence integrity.
    """

    def process(self, bundle: ContextBundle) -> ContextBundle:
        logger.info(f"Agent {self.name} preparing dispatch payload...")
        
        forensic = bundle.artifacts.get("forensic_audit", {})
        if forensic.get("recommendation") != "escalate":
            return bundle
            
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Audit Result: {json.dumps(forensic)}"}
        ]
        
        try:
            draft = self.call_llm(messages)
            bundle.add_artifact("dispatch_draft", draft)
            
            # Logic to actually call BrevoDispatcher could go here in 2026 ADK pattern
            # For now, we store the artifact for the final decision_engine step.
            
        except Exception as e:
            logger.error(f"Messenger Agent error: {e}")
            
        return bundle
