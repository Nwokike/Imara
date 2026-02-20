import logging
import requests
import threading
import time
from datetime import datetime
from typing import Optional
from django.utils import timezone
from django.conf import settings
from dispatch.tasks import send_email_task

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
MAX_RETRIES = 3
RETRY_DELAY = 2


class BrevoDispatcherError(Exception):
    pass


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
        
        if self._available:
            self.headers = {
                "api-key": self.api_key,
                "Content-Type": "application/json"
            }
        else:
            self.headers = {}
            logger.warning("BREVO_API_KEY not found in settings - Email dispatch will be disabled")
        
        self.sender_email = getattr(settings, 'BREVO_SENDER_EMAIL', 'imara-alerts@projectimara.org')
        self.sender_name = "Project Imara Alert System"
        
        BrevoDispatcher._initialized = True
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def send_forensic_alert(
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
        agent_artifacts: dict = None
    ) -> dict:
        if not self._available:
            logger.warning("Brevo API not configured - email dispatch skipped")
            return {
                "success": False,
                "error": "Email service not configured",
                "recipient": recipient_email
            }
        
        from django.template.loader import render_to_string
        
        risk_color = "#dc3545" if risk_score >= 7 else "#ffc107" if risk_score >= 4 else "#28a745"
        risk_level = "CRITICAL" if risk_score >= 7 else "MODERATE" if risk_score >= 4 else "LOW"
        
        artifacts = agent_artifacts or {}
        
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
            'safety_check': artifacts.get('safety_check'),
            'vision_analysis': artifacts.get('vision_analysis'),
            'translation': artifacts.get('translation')
        }
        
        html_content = render_to_string('dispatch/forensic_alert.html', context)
        subject = f"OFFICIAL FORENSIC ALERT - Case #{str(case_id)[:8].upper()}"
        
        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [{"email": recipient_email}],
            "bcc": [{"email": settings.ADMIN_NOTIFICATION_EMAIL}],
            "subject": subject,
            "htmlContent": html_content
        }
        
        # Note: attachment logic can be added here if needed in the future
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    BREVO_API_URL,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"Forensic alert sent successfully to {recipient_email}, Message ID: {result.get('messageId')}")
                
                return {
                    "success": True,
                    "message_id": result.get("messageId"),
                    "recipient": recipient_email
                }
                
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"Brevo API timeout (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    import time
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    last_error = e
                    logger.warning(f"Brevo rate limited (attempt {attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1:
                        import time
                        time.sleep(RETRY_DELAY * (attempt + 1) * 2)
                else:
                    logger.error(f"Brevo API error: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "recipient": recipient_email
                    }
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Brevo request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    import time
                    time.sleep(RETRY_DELAY * (attempt + 1))
        
        logger.error(f"Failed to send forensic alert after {MAX_RETRIES} attempts: {last_error}")
        return {
            "success": False,
            "error": str(last_error),
            "recipient": recipient_email
        }
    
    def _generate_forensic_email_html(self, *args, **kwargs):
        # Deprecated: logic moved to Django template
        pass
    
    def send_async(
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
        dispatch_log_id: Optional[int] = None,
        incident_id: Optional[int] = None,
    ) -> None:
        """
        Enqueues the email sending task to Huey.
        """
        if not self._available:
            logger.warning("Brevo API not configured - skipping async dispatch")
            return

        from django.template.loader import render_to_string
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
            'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        html_content = render_to_string('dispatch/forensic_alert.html', context)
        subject = f"OFFICIAL FORENSIC ALERT - Case #{str(case_id)[:8].upper()}"
        
        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [{"email": recipient_email}],
            "bcc": [{"email": settings.ADMIN_NOTIFICATION_EMAIL}],
            "subject": subject,
            "htmlContent": html_content
        }
        
        # Dispatch to Huey
        send_email_task(payload, dispatch_log_id=dispatch_log_id, incident_id=incident_id)
        logger.info(f"Huey task queued for case {case_id[:8]} to {recipient_email}")


    def send_user_confirmation(
        self,
        user_email: str,
        case_id: str,
        partner_name: str,
        partner_email: str,
        risk_score: int,
        summary: str,
        location: str
    ) -> dict:
        if not self._available:
            logger.warning("Brevo API not configured - user confirmation skipped")
            return {"success": False, "error": "Email service not configured"}
        
        from django.template.loader import render_to_string
        context = {
            'case_id': case_id,
            'partner_name': partner_name,
            'partner_email': partner_email,
            'risk_score': risk_score,
            'summary': summary,
            'location': location,
            'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        html_content = render_to_string('dispatch/user_confirmation.html', context)
        subject = f"Your Report Has Been Submitted - Case #{str(case_id)[:8].upper()}"
        
        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [{"email": user_email}],
            "subject": subject,
            "htmlContent": html_content
        }
        
        try:
            response = requests.post(
                BREVO_API_URL,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"User confirmation sent to {user_email}")
            return {"success": True, "message_id": result.get("messageId")}
        except Exception as e:
            logger.error(f"Failed to send user confirmation: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_user_confirmation_html(self, *args, **kwargs):
        # Deprecated: logic moved to Django template
        pass
    
    def send_user_confirmation_async(
        self,
        user_email: str,
        case_id: str,
        partner_name: str,
        partner_email: str,
        risk_score: int,
        summary: str,
        location: str
    ) -> None:
        if not self._available:
            return

        from django.template.loader import render_to_string
        context = {
            'case_id': case_id,
            'partner_name': partner_name,
            'partner_email': partner_email,
            'risk_score': risk_score,
            'summary': summary,
            'location': location,
            'timestamp': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        html_content = render_to_string('dispatch/user_confirmation.html', context)
        subject = f"Your Report Has Been Submitted - Case #{str(case_id)[:8].upper()}"
        
        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [{"email": user_email}],
            "subject": subject,
            "htmlContent": html_content
        }
        
        send_email_task(payload)
        logger.info(f"Huey user confirmation task queued for {user_email}")
    
    def send_user_confirmation_async(
        self,
        user_email: str,
        case_id: str,
        partner_name: str,
        partner_email: str,
        risk_score: int,
        summary: str,
        location: str
    ) -> None:
        if not self._available:
            return

        subject = f"Your Report Has Been Submitted - Case #{str(case_id)[:8].upper()}"
        
        html_content = self._generate_user_confirmation_html(
            case_id=case_id,
            partner_name=partner_name,
            partner_email=partner_email,
            risk_score=risk_score,
            summary=summary,
            location=location
        )
        
        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [{"email": user_email}],
            "subject": subject,
            "htmlContent": html_content
        }
        
        send_email_task(payload)
        logger.info(f"Huey user confirmation task queued for {user_email}")


def get_brevo_dispatcher() -> Optional[BrevoDispatcher]:
    dispatcher = BrevoDispatcher()
    return dispatcher if dispatcher.is_available else None


brevo_dispatcher = BrevoDispatcher()
