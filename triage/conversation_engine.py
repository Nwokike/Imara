"""
Platform-Agnostic Conversation Engine for Project Imara

This module provides a unified conversation handling system that works
across all messaging platforms (Telegram, WhatsApp, Instagram, Discord, etc.)

The engine manages:
- Multi-turn conversational state
- Evidence gathering with empathetic dialogue
- Location collection (mandatory for high-risk cases)
- Confirmation before report submission
- Language detection and localized responses
"""

import logging
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from django.conf import settings

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    """States in the conversation state machine."""
    IDLE = 'IDLE'
    GATHERING = 'GATHERING'
    ASKING_LOCATION = 'ASKING_LOCATION'
    CONFIRMING = 'CONFIRMING'
    PROCESSING = 'PROCESSING'
    LOW_RISK_ADVISE = 'LOW_RISK_ADVISE'


@dataclass
class ConversationResponse:
    """Response from the conversation engine."""
    message: str
    state: ConversationState
    gathered_info: Dict[str, Any] = field(default_factory=dict)
    should_create_report: bool = False
    is_low_risk: bool = False
    detected_language: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'message': self.message,
            'state': self.state.value,
            'gathered_info': self.gathered_info,
            'should_create_report': self.should_create_report,
            'is_low_risk': self.is_low_risk,
            'detected_language': self.detected_language,
            'error': self.error
        }


# System prompt for conversational AI
CONVERSATIONAL_SYSTEM_PROMPT = """You are Imara, a compassionate AI protector for women and girls facing online violence in Africa.

PERSONALITY:
- Warm, empathetic, patient - like a trusted sister who listens first
- Never judgmental, always supportive
- Professional but caring

YOUR MISSION:
You are having a CONVERSATION, not classifying a single message.
NEVER immediately jump to creating a report. ALWAYS engage in dialogue first.

CRITICAL RULES:
1. For HIGH RISK threats (score 7+), you MUST collect location before processing
2. ALWAYS confirm understanding before creating reports
3. For LOW RISK (insults, rude comments), give advice directly
4. If user seems scared/in danger, prioritize safety with immediate resources
5. Match the user's language (English, Pidgin, Swahili, French, etc.)

CONVERSATION FLOW:
1. GREET & LISTEN - Acknowledge their message, show empathy
2. GATHER INFO - If unclear, ask:
   - "Can you tell me more about what happened?"
   - "When did this occur?"
   - "Do you know who sent this?"
3. GET LOCATION - For high-risk cases, ALWAYS ask:
   - "To connect you with the right authorities, which city/country are you in?"
4. CONFIRM - Before filing report, summarize and confirm:
   - "Here's what I understood: [summary]. Should I file a report? (Yes/No)"
5. PROCESS - Only after "Yes" confirmation

RESPONSE FORMAT (JSON only):
{
  "response": "<your empathetic message to the user>",
  "state": "IDLE|GATHERING|ASKING_LOCATION|CONFIRMING|PROCESSING|LOW_RISK_ADVISE",
  "gathered_info": {
    "threat_type": "<harassment|threat|doxing|blackmail|stalking|sextortion|insult|other>",
    "location": "<city, country if provided>",
    "risk_level": "<low|medium|high>",
    "risk_score": <1-10>,
    "evidence_summary": "<brief summary of what they shared>",
    "perpetrator_info": "<any info about the abuser if provided>"
  },
  "detected_language": "<english|pidgin|swahili|french|hausa|yoruba|igbo|other>"
}

EXAMPLE CONVERSATIONS:

---
User: "Help"
Response: {
  "response": "I'm here for you 💜 You're safe with me. Can you tell me what's happening?",
  "state": "GATHERING",
  "gathered_info": {},
  "detected_language": "english"
}

---
User: "Someone is threatening to share my nude pictures"
Response: {
  "response": "I'm so sorry you're going through this 💜 What you're describing is sextortion - this is a serious crime and NOT your fault.\\n\\nTo help connect you with the right authorities, please tell me: Which city and country are you in?",
  "state": "ASKING_LOCATION",
  "gathered_info": {
    "threat_type": "sextortion",
    "risk_level": "high",
    "risk_score": 8,
    "evidence_summary": "Threat to share intimate images"
  },
  "detected_language": "english"
}

---
User: "Lagos"
Response: {
  "response": "Thank you. I've noted you're in Lagos, Nigeria.\\n\\n📋 *Here's what I understood:*\\n• Threat type: Sextortion (threats to share intimate images)\\n• Location: Lagos, Nigeria\\n• This is a HIGH RISK situation (8/10)\\n\\nI can file a report with Nigerian cybercrime authorities who handle these cases.\\n\\n*Would you like me to proceed?* Reply YES to file the report, or tell me if anything needs to change.",
  "state": "CONFIRMING",
  "gathered_info": {
    "threat_type": "sextortion",
    "location": "Lagos, Nigeria",
    "risk_level": "high",
    "risk_score": 8,
    "evidence_summary": "Threat to share intimate images"
  },
  "detected_language": "english"
}

---
User: "Yes"
Response: {
  "response": "✅ Filing your report now with Nigerian cybercrime authorities...",
  "state": "PROCESSING",
  "gathered_info": {
    "threat_type": "sextortion",
    "location": "Lagos, Nigeria",
    "risk_level": "high",
    "risk_score": 8,
    "evidence_summary": "Threat to share intimate images",
    "user_confirmed": true
  },
  "detected_language": "english"
}

---
User: "Someone called me ugly on Facebook"
Response: {
  "response": "I'm sorry someone said that to you 💜 Mean comments hurt, even when we try to ignore them.\\n\\n💡 *My advice:*\\n• Block and report the person on Facebook\\n• Don't engage - trolls feed on reactions\\n• Screenshot it for your records if it continues\\n• Remember: their words say nothing about your worth\\n\\nIf the harassment continues or escalates, come back and I'll help you escalate.\\n\\nYou're not alone. 🛡️",
  "state": "LOW_RISK_ADVISE",
  "gathered_info": {
    "threat_type": "insult",
    "risk_level": "low",
    "risk_score": 2,
    "evidence_summary": "Verbal insult on social media"
  },
  "detected_language": "english"
}

---
Pidgin Example:
User: "Dem dey threaten to kill me o"
Response: {
  "response": "Ah! E serious o. No worry, I dey here with you 💜\\n\\nDeath threat na very serious matter. Abeg tell me - which city and country you dey?",
  "state": "ASKING_LOCATION",
  "gathered_info": {
    "threat_type": "death_threat",
    "risk_level": "high",
    "risk_score": 9,
    "evidence_summary": "Death threat received"
  },
  "detected_language": "pidgin"
}

REMEMBER:
- You are CONVERSING, not just classifying
- Be warm and human, not robotic
- High risk = MUST get location before processing
- ALWAYS confirm before creating formal reports
- Match their language and tone"""


class ConversationEngine:
    """
    Platform-agnostic conversation engine for Project Imara.
    
    Handles multi-turn conversations with proper state management,
    evidence collection, and empathetic dialogue.
    """
    
    def __init__(self):
        self._groq_client = None
    
    @property
    def groq_client(self):
        """Lazy-load Groq client."""
        if self._groq_client is None:
            from triage.clients.groq_client import get_groq_client
            self._groq_client = get_groq_client()
        return self._groq_client
    
    def process_message(
        self,
        session,
        user_message: str,
        message_type: str = 'text'
    ) -> ConversationResponse:
        """
        Process a user message within a conversation session.
        
        Args:
            session: ChatSession instance
            user_message: The user's message text
            message_type: Type of message (text, image, voice, etc.)
        
        Returns:
            ConversationResponse with the AI's response and state updates
        """
        try:
            # Build conversation history for context (last 15 messages with timestamps)
            conversation_history = session.get_messages_for_llm(limit=15)
            
            # Add current user message (without timestamp - it's "now")
            conversation_history.append({
                'role': 'user',
                'content': user_message
            })
            
            # Build rich context for AI
            context_parts = []
            
            # Include gathered evidence if any
            if session.gathered_evidence:
                context_parts.append(f"GATHERED EVIDENCE SO FAR:\n{json.dumps(session.gathered_evidence, indent=2)}")
            
            # Include current state
            context_parts.append(f"CURRENT CONVERSATION STATE: {session.conversation_state}")
            
            # Include user's known info
            if session.last_detected_location:
                context_parts.append(f"USER'S KNOWN LOCATION: {session.last_detected_location}")
            if session.language_preference:
                context_parts.append(f"USER'S LANGUAGE: {session.language_preference}")
            
            # Include conversation history summary for past context
            history_summary = session.get_conversation_history_summary()
            context_parts.append(f"\n{history_summary}")
            
            additional_context = "\n\n".join(context_parts)
            
            # Make API call
            response = self._call_llm(
                conversation_history,
                additional_context
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Conversation engine error: {e}")
            return ConversationResponse(
                message="I'm having a moment of trouble. Please try again, or if it's urgent, type HELP for emergency resources.",
                state=ConversationState.IDLE,
                error=str(e)
            )
    
    def _call_llm(
        self, 
        messages: List[Dict[str, str]],
        additional_context: str = ""
    ) -> ConversationResponse:
        """Call the LLM with conversation history."""
        import requests
        import os
        
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            return self._get_fallback_response()
        
        system_prompt = CONVERSATIONAL_SYSTEM_PROMPT + additional_context
        
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages
        
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                    "messages": full_messages,
                    "temperature": 0.3,  # Slightly more creative for conversation
                    "max_tokens": 800,
                    "response_format": {"type": "json_object"}
                },
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            return self._parse_llm_response(content)
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return self._get_fallback_response()
    
    def _parse_llm_response(self, content: str) -> ConversationResponse:
        """Parse the LLM's JSON response."""
        try:
            data = json.loads(content)
            
            state_str = data.get('state', 'GATHERING').upper()
            try:
                state = ConversationState(state_str)
            except ValueError:
                state = ConversationState.GATHERING
            
            gathered_info = data.get('gathered_info', {})
            
            # Determine if we should create a report
            should_create_report = state == ConversationState.PROCESSING
            is_low_risk = state == ConversationState.LOW_RISK_ADVISE
            
            return ConversationResponse(
                message=data.get('response', "I'm here to help. Can you tell me more?"),
                state=state,
                gathered_info=gathered_info,
                should_create_report=should_create_report,
                is_low_risk=is_low_risk,
                detected_language=data.get('detected_language')
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return ConversationResponse(
                message=content if content else "I'm here to help. Can you tell me more about what happened?",
                state=ConversationState.GATHERING,
                error="JSON parse error"
            )
    
    def _get_fallback_response(self) -> ConversationResponse:
        """Fallback response when AI is unavailable."""
        return ConversationResponse(
            message="I'm here for you 💜 Can you tell me what's happening? I'm listening.",
            state=ConversationState.GATHERING,
            error="AI service unavailable"
        )
    
    def handle_safe_word(self, session) -> ConversationResponse:
        """Handle safe word triggers (STOP, HELP, etc.)."""
        session.reset_conversation()
        
        safety_message = """🛡️ *SAFE MODE ACTIVATED*

I've stopped processing. Your safety comes first.

*Immediate help:*
🇳🇬 Nigeria: 0800-CALLNOW (0800-225-5669)
🇰🇪 Kenya: 1195 (Gender Violence)
🇿🇦 South Africa: 0800-428-428

*Remember:*
• Delete this chat if needed
• You can start fresh anytime
• You are NOT alone

Type anything when you're ready to talk again."""
        
        return ConversationResponse(
            message=safety_message,
            state=ConversationState.IDLE
        )


# Singleton instance
conversation_engine = ConversationEngine()
