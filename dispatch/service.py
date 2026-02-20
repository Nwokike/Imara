import logging
import httpx
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string
from dispatch.tasks import send_email_task

logger = logging.getLogger(__name__)

class BrevoDispatcher:
    _instance = None
    _initialized = False
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if BrevoDispatcher._initialized:
            return
        
        self.api_key = getattr(settings, 'BREVO_API_KEY', None)
        self._available = bool(self.api_key)
        self.sender_email = getattr(settings, 'BREVO_SENDER_EMAIL', 'imara-alerts@projectimara.org')
        self.sender_name = "Imara Alert System"
        
        BrevoDispatcher._initialized = True
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def send_forensic_alert_async(
        self,
        recipient_email: str,
        case_id: str,
        evidence_text: str,
        risk_score: int,
        threat_type: str,
        location: str,
        chain_hash: str,
        summary: str,
        source: str = "Web Form",
        agent_artifacts: dict = None,
        dispatch_log_id: int = None,
        incident_id: int = None
    ) -> None:
        """Enqueues a high-priority forensic alert for background delivery."""
        if not self._available: return

        risk_color = "#dc3545" if risk_score >= 7 else "#ffc107" if risk_score >= 4 else "#28a745"
        risk_level = "CRITICAL" if risk_score >= 7 else "MODERATE" if risk_score >= 4 else "LOW"
        
        context = {
            'case_id': case_id,
            'evidence_text': evidence_text,
            'risk_score': risk_score,
            'risk_color': risk_color,
            'risk_level': risk_level,
            'threat_type': threat_type,
            'location': location,
            'chain_hash': chain_hash,
            'summary': summary,
            'source': source,
            'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            'safety_check': (agent_artifacts or {}).get('safety_check'),
            'vision_analysis': (agent_artifacts or {}).get('vision_analysis'),
            'translation': (agent_artifacts or {}).get('translation')
        }
        
        html_content = render_to_string('dispatch/forensic_alert.html', context)
        payload = {
            "sender": {"name": self.sender_name, "email": self.sender_email},
            "to": [{"email": recipient_email}],
            "bcc": [{"email": settings.ADMIN_NOTIFICATION_EMAIL}],
            "subject": f"OFFICIAL FORENSIC ALERT - Case #{str(case_id)[:8].upper()}",
            "htmlContent": html_content
        }
        
        send_email_task.enqueue(payload, dispatch_log_id=dispatch_log_id, incident_id=incident_id)

    def send_user_confirmation_async(
        self,
        user_email: str,
        case_id: str,
        partner_name: Optional[str],
        partner_email: Optional[str],
        risk_score: int,
        summary: str,
        location: Optional[str]
    ) -> None:
        """Enqueues a user confirmation email."""
        if not self._available: return

        context = {
            'case_id': case_id,
            'partner_name': partner_name or "Support Partner",
            'partner_email': partner_email or "",
            'risk_score': risk_score,
            'summary': summary,
            'location': location or "Unknown",
            'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        html_content = render_to_string('dispatch/user_confirmation.html', context)
        payload = {
            "sender": {"name": self.sender_name, "email": self.sender_email},
            "to": [{"email": user_email}],
            "subject": f"Your Report Has Been Submitted - Case #{str(case_id)[:8].upper()}",
            "htmlContent": html_content
        }
        
        send_email_task.enqueue(payload)

    def send_async(self, **kwargs):
        """Legacy wrapper for backward compatibility."""
        return self.send_forensic_alert_async(**kwargs)

brevo_dispatcher = BrevoDispatcher()
