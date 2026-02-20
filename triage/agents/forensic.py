"""
Forensic Agent - Legal and Chain-of-Custody Expert.
Focus: Deep reasoning, legal verification, and evidence integrity.
Tool: Evidence Hasher
Model: openai/gpt-oss-120b
"""
import logging
import json
import hashlib
from .base import BaseAgent, ContextBundle

logger = logging.getLogger(__name__)

class ForensicAgent(BaseAgent):
    name = "forensic"
    role = "Legal Technologist"
    model_alias = "forensic-expert"
    
    SYSTEM_PROMPT = """
    Assess this incident for legal admissibility and forensic integrity.
    Provide a professional summary suitable for law enforcement or NGO partners.
    
    RESPOND IN JSON FORMAT ONLY:
    {
        "forensic_summary": "<expert summary>",
        "legal_category": "<type of crime>",
        "urgency_rating": 1-10,
        "recommendation": "escalate|monitor|advice"
    }
    """

    def process(self, bundle: ContextBundle) -> ContextBundle:
        logger.info(f"Agent {self.name} conducting forensic audit...")
        
        # Consolidate all gathered evidence for reasoning
        artifacts_json = json.dumps(bundle.artifacts, indent=2)
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Gathered Evidence:
{artifacts_json}

User Input: {bundle.user_message}"}
        ]
        
        try:
            response_text = self.call_llm(messages, response_format={"type": "json_object"})
            result = json.loads(response_text)
            
            # Add forensic artifact
            bundle.add_artifact("forensic_audit", result)
            
            # Generate cryptographic evidence hash if not present
            content_to_hash = f"{bundle.user_message}{artifacts_json}"
            bundle.add_artifact("forensic_hash", hashlib.sha256(content_to_hash.encode()).hexdigest())
            
        except Exception as e:
            logger.error(f"Forensic Agent error: {e}")
            
        return bundle
