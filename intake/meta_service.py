"""
Meta Platform (Facebook Messenger / Instagram) Service Module

This module handles outbound messaging to Meta's Messenger and Instagram APIs.
Mirrors the pattern used for other platform services in Project Imara.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MetaMessagingService:
    """
    Service for sending messages via Meta's Send API.
    Supports both Facebook Messenger and Instagram messaging.
    """
    
    MESSENGER_API_URL = "https://graph.facebook.com/v21.0/me/messages"
    
    def __init__(self):
        self.access_token = settings.META_PAGE_ACCESS_TOKEN
    
    def send_text_message(self, recipient_id: str, text: str, platform: str = "messenger") -> bool:
        """
        Send a text message to a user.
        
        Args:
            recipient_id: The PSID (Page-Scoped ID) of the recipient
            text: The message text to send
            platform: 'messenger' or 'instagram'
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.access_token:
            logger.error("META_PAGE_ACCESS_TOKEN not configured")
            return False
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "messaging_type": "RESPONSE"
        }
        
        try:
            response = requests.post(
                self.MESSENGER_API_URL,
                params={"access_token": self.access_token},
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Message sent to {recipient_id} via Meta {platform}")
                return True
            else:
                logger.error(f"Meta Send API error: {response.status_code} - {response.text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Meta Send API request failed: {e}")
            return False
    
    def send_typing_indicator(self, recipient_id: str, action: str = "typing_on") -> bool:
        """
        Send a typing indicator to show the bot is processing.
        
        Args:
            recipient_id: The PSID of the recipient
            action: 'typing_on' or 'typing_off'
            
        Returns:
            True if successful, False otherwise
        """
        if not self.access_token:
            return False
        
        payload = {
            "recipient": {"id": recipient_id},
            "sender_action": action
        }
        
        try:
            response = requests.post(
                self.MESSENGER_API_URL,
                params={"access_token": self.access_token},
                json=payload,
                timeout=10
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def send_message_with_buttons(
        self, 
        recipient_id: str, 
        text: str, 
        buttons: list,
        platform: str = "messenger"
    ) -> bool:
        """
        Send a message with quick reply buttons for feedback.
        
        Args:
            recipient_id: The PSID of the recipient
            text: The message text
            buttons: List of button dicts with 'title' and 'payload' keys
            platform: 'messenger' or 'instagram'
            
        Returns:
            True if successful, False otherwise
        """
        if not self.access_token:
            logger.error("META_PAGE_ACCESS_TOKEN not configured")
            return False
        
        quick_replies = [
            {
                "content_type": "text",
                "title": btn.get("title", ""),
                "payload": btn.get("payload", "")
            }
            for btn in buttons[:11]  # Meta limits to 11 quick replies
        ]
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "text": text,
                "quick_replies": quick_replies
            },
            "messaging_type": "RESPONSE"
        }
        
        try:
            response = requests.post(
                self.MESSENGER_API_URL,
                params={"access_token": self.access_token},
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Button message sent to {recipient_id} via Meta {platform}")
                return True
            else:
                logger.error(f"Meta Send API error: {response.status_code} - {response.text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Meta Send API request failed: {e}")
            return False


# Singleton instance for use across the application
meta_messenger = MetaMessagingService()
