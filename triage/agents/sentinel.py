"""
Safety Sentinel Agent - Imara's First Line of Defense.
Focus: Content classification against customizable safety policies.
Tool: Policy Filter
Model: gpt-oss-safeguard-20b
"""
import logging
import json
from .base import BaseAgent, ContextBundle

logger = logging.getLogger(__name__)

class SentinelAgent(BaseAgent):
    name = "sentinel"
    role = "Safety Guardian"
    model_alias = "safety-sentinel"
    
    POLICY_PROMPT = """
    Analyze the following message against Imara's protection policy for women and girls.
    DETERMINE if the message contains:
    1. Direct threats of violence.
    2. Stalking or persistent harassment.
    3. Doxing (leak of private info).
    4. Blackmail or sextortion.
    5. Toxic insults.

    RESPOND IN JSON FORMAT ONLY:
    {
        "is_safe": <boolean>,
        "risk_level": "low|medium|high|critical",
        "policy_violation": "<type or none>",
        "reasoning": "<brief explanation>"
    }
    """

    def process(self, bundle: ContextBundle) -> ContextBundle:
        logger.info(f"Agent {self.name} processing message...")
        
        messages = [
            {"role": "system", "content": self.POLICY_PROMPT},
            {"role": "user", "content": bundle.user_message}
        ]
        
        try:
            response_text = self.call_llm(messages, response_format={"type": "json_object"})
            analysis = json.loads(response_text)
            
            bundle.add_artifact("safety_check", analysis)
            bundle.workflow_state = "SAFE" if analysis.get("is_safe") else "THREAT_DETECTED"
            
        except Exception as e:
            logger.error(f"Sentinel Agent error: {e}")
            bundle.add_artifact("safety_check", {"error": str(e), "is_safe": True}) # Fail safe
            
        return bundle
