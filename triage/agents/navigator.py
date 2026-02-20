"""
Navigator Agent - Jurisdictional Specialist.
Focus: Location detection and partner routing.
Tool: Location Resolver
Model: llama-3.3-70b-versatile
"""
import logging
import json
from .base import BaseAgent, ContextBundle

logger = logging.getLogger(__name__)

class NavigatorAgent(BaseAgent):
    name = "navigator"
    role = "Routing Specialist"
    model_alias = "triage-navigator"
    
    SYSTEM_PROMPT = """
    Identify the victim's location (City and Country) from the conversation history and current message.
    Cross-reference against major African cities.
    
    RESPOND IN JSON FORMAT ONLY:
    {
        "location": "<City, Country>",
        "confidence": <0.0-1.0>,
        "is_africa": <boolean>,
        "needs_ask": <boolean>
    }
    """

    def process(self, bundle: ContextBundle) -> ContextBundle:
        logger.info(f"Agent {self.name} resolving location...")
        
        history = "
".join([f"{m['role']}: {m['content']}" for m in bundle.conversation_history[-5:]])
        user_input = f"History:
{history}

Current Message: {bundle.user_message}"
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]
        
        try:
            response_text = self.call_llm(messages, response_format={"type": "json_object"})
            result = json.loads(response_text)
            
            # Normalize via partner utility
            from partners.utils import normalize_location
            normalized = normalize_location(result.get("location", ""))
            
            bundle.add_artifact("location_analysis", {
                "raw_location": result.get("location"),
                "normalized_country": normalized,
                "needs_ask": result.get("needs_ask", False)
            })
            
        except Exception as e:
            logger.error(f"Navigator Agent error: {e}")
            
        return bundle
