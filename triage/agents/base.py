"""
Base Agent and Context Bundle definitions for Imara's Multi-Agent Network.
Inspired by Google ADK 2026 but optimized for low-memory Django environments.
"""
import logging
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from utils.llm_router import get_llm_router

logger = logging.getLogger(__name__)

@dataclass
class ContextBundle:
    """
    The 'Source of Truth' that travels between agents.
    Contains evidence, state, and history.
    """
    user_message: str
    message_type: str = "text"
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    workflow_state: str = "START"
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

    def add_artifact(self, key: str, value: Any):
        self.artifacts[key] = value

class BaseAgent:
    """
    Abstract base class for all specialized agents.
    Pattern: One Agent, One Tool, One Role.
    """
    name: str = "base_agent"
    role: str = "Generic Assistant"
    model_alias: str = "chat-counselor" # Default alias from litellm_config.yaml
    
    def __init__(self):
        self.router = get_llm_router()

    def process(self, bundle: ContextBundle) -> ContextBundle:
        """
        Main entry point for agent logic.
        Must be overridden by specialized agents.
        """
        raise NotImplementedError("Each agent must implement the process method.")

    def call_llm(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Unified LLM caller with LiteLLM fallback routing.
        """
        try:
            response = self.router.completion(
                model=self.model_alias,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Agent {self.name} LLM call failed: {e}")
            raise e
