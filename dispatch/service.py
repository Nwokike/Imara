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
        source: str = "Web Form"
    ) -> dict:
        if not self._available:
            logger.warning("Brevo API not configured - email dispatch skipped")
            return {
                "success": False,
                "error": "Email service not configured",
                "recipient": recipient_email
            }
        
        subject = f"OFFICIAL FORENSIC ALERT - Case #{str(case_id)[:8].upper()}"
        
        html_content = self._generate_forensic_email_html(
            case_id=case_id,
            evidence_text=evidence_text,
            risk_score=risk_score,
            threat_type=threat_type,
            location=location,
            chain_hash=chain_hash,
            summary=summary,
            source=source
        )
        
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
    
    def _generate_forensic_email_html(
        self,
        case_id: str,
        evidence_text: str,
        risk_score: int,
        threat_type: str,
        location: str,
        chain_hash: str,
        summary: str,
        source: str
    ) -> str:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        risk_color = "#dc3545" if risk_score >= 7 else "#ffc107" if risk_score >= 4 else "#28a745"
        risk_level = "CRITICAL" if risk_score >= 7 else "MODERATE" if risk_score >= 4 else "LOW"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 650px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 30px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 2px;">
                    OFFICIAL FORENSIC ALERT
                </h1>
                <p style="color: #e94560; margin: 10px 0 0 0; font-size: 16px; font-weight: bold;">
                    PROJECT IMARA - Digital Safety System
                </p>
            </td>
        </tr>
        
        <tr>
            <td style="background-color: {risk_color}; padding: 15px; text-align: center;">
                <span style="color: #ffffff; font-size: 18px; font-weight: bold;">
                    {risk_level} THREAT DETECTED - IMMEDIATE ATTENTION REQUIRED
                </span>
            </td>
        </tr>
        
        <tr>
            <td style="padding: 30px;">
                <table width="100%" style="border-collapse: collapse; margin-bottom: 25px;">
                    <tr>
                        <td style="padding: 12px; background-color: #f8f9fa; border-left: 4px solid #e94560;">
                            <strong style="color: #1a1a2e;">Case ID:</strong>
                            <span style="color: #495057; font-family: monospace;">{str(case_id)[:8].upper()}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; background-color: #ffffff; border-left: 4px solid #e94560;">
                            <strong style="color: #1a1a2e;">Timestamp:</strong>
                            <span style="color: #495057;">{timestamp}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; background-color: #f8f9fa; border-left: 4px solid #e94560;">
                            <strong style="color: #1a1a2e;">Source:</strong>
                            <span style="color: #495057;">{source}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; background-color: #ffffff; border-left: 4px solid #e94560;">
                            <strong style="color: #1a1a2e;">Detected Location:</strong>
                            <span style="color: #495057;">{location or 'Unknown'}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; background-color: #f8f9fa; border-left: 4px solid #e94560;">
                            <strong style="color: #1a1a2e;">Threat Type:</strong>
                            <span style="color: #495057; text-transform: uppercase;">{threat_type or 'Unclassified'}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; background-color: #ffffff; border-left: 4px solid #e94560;">
                            <strong style="color: #1a1a2e;">Risk Score:</strong>
                            <span style="color: {risk_color}; font-weight: bold; font-size: 18px;">{risk_score}/10</span>
                        </td>
                    </tr>
                </table>
                
                <div style="background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin-bottom: 25px;">
                    <h3 style="color: #856404; margin: 0 0 10px 0; font-size: 14px;">AI THREAT SUMMARY</h3>
                    <p style="color: #856404; margin: 0; font-size: 14px;">{summary}</p>
                </div>
                
                <div style="background-color: #1a1a2e; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h3 style="color: #e94560; margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase;">EVIDENCE CONTENT</h3>
                    <div style="background-color: #16213e; border-radius: 4px; padding: 15px; border-left: 3px solid #e94560;">
                        <pre style="color: #ffffff; margin: 0; white-space: pre-wrap; word-wrap: break-word; font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.5;">{evidence_text or 'No text content available'}</pre>
                    </div>
                </div>
                
                <div style="background-color: #d4edda; border: 1px solid #28a745; border-radius: 8px; padding: 15px; margin-bottom: 25px;">
                    <h3 style="color: #155724; margin: 0 0 10px 0; font-size: 14px;">CHAIN OF CUSTODY VERIFICATION</h3>
                    <p style="color: #155724; margin: 0; font-size: 12px;">
                        <strong>SHA-256 Hash:</strong><br>
                        <code style="background-color: #c3e6cb; padding: 5px 10px; border-radius: 4px; font-size: 11px; word-break: break-all;">{chain_hash or 'Not yet computed'}</code>
                    </p>
                    <p style="color: #155724; margin: 10px 0 0 0; font-size: 11px;">
                        This cryptographic hash ensures evidence integrity and can be used for legal verification.
                    </p>
                </div>
                
                <div style="background-color: #f8d7da; border: 1px solid #dc3545; border-radius: 8px; padding: 15px;">
                    <h3 style="color: #721c24; margin: 0 0 10px 0; font-size: 14px;">ACTION REQUIRED</h3>
                    <p style="color: #721c24; margin: 0; font-size: 13px;">
                        This report has been automatically flagged due to potential threats against a woman or girl. 
                        Please review the evidence and take appropriate action according to your jurisdiction's protocols.
                    </p>
                </div>
            </td>
        </tr>
        
        <tr>
            <td style="background-color: #1a1a2e; padding: 25px; text-align: center;">
                <p style="color: #ffffff; margin: 0 0 10px 0; font-size: 14px; font-weight: bold;">
                    Project Imara - Protecting Women and Girls Online
                </p>
                <p style="color: #a0a0a0; margin: 0; font-size: 11px;">
                    "Imara" means "Strong" in Swahili. Together, we stand against online gender-based violence.
                </p>
                <p style="color: #a0a0a0; margin: 10px 0 0 0; font-size: 10px;">
                    This is an automated alert from Project Imara's AI-powered threat detection system.
                    <br>Report generated: {timestamp}
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html
    
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

        html_content = self._generate_forensic_email_html(
            case_id=case_id,
            evidence_text=evidence_text,
            risk_score=risk_score,
            threat_type=threat_type,
            location=location,
            chain_hash=chain_hash,
            summary=summary,
            source=source
        )
        
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
    
    def _generate_user_confirmation_html(
        self,
        case_id: str,
        partner_name: str,
        partner_email: str,
        risk_score: int,
        summary: str,
        location: str
    ) -> str:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="background: linear-gradient(135deg, #6B4C9A 0%, #4A3570 100%); padding: 25px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 22px;">
                    Project Imara
                </h1>
                <p style="color: #D6BCFA; margin: 8px 0 0 0; font-size: 14px;">
                    Your Digital Bodyguard
                </p>
            </td>
        </tr>
        
        <tr>
            <td style="padding: 25px;">
                <div style="background-color: #d4edda; border: 1px solid #28a745; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
                    <h2 style="color: #155724; margin: 0; font-size: 18px;">Your Report Has Been Submitted</h2>
                </div>
                
                <p style="color: #333; font-size: 14px; line-height: 1.6;">
                    We want to confirm that your report has been received and shared with the appropriate support partner. Here are the details:
                </p>
                
                <table width="100%" style="border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 10px; background-color: #f8f9fa; border-left: 4px solid #6B4C9A;">
                            <strong>Case ID:</strong> {str(case_id)[:8].upper()}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-left: 4px solid #6B4C9A;">
                            <strong>Risk Level:</strong> {risk_score}/10
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; background-color: #f8f9fa; border-left: 4px solid #6B4C9A;">
                            <strong>Location Detected:</strong> {location or 'Unknown'}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-left: 4px solid #6B4C9A;">
                            <strong>Summary:</strong> {summary}
                        </td>
                    </tr>
                </table>
                
                <div style="background-color: #e7f3ff; border: 1px solid #0066cc; border-radius: 8px; padding: 15px; margin: 20px 0;">
                    <h3 style="color: #004085; margin: 0 0 10px 0; font-size: 14px;">REPORT SHARED WITH:</h3>
                    <p style="color: #004085; margin: 0; font-size: 14px;">
                        <strong>{partner_name}</strong><br>
                        <span style="font-size: 13px;">{partner_email}</span>
                    </p>
                </div>
                
                <div style="background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px;">
                    <h3 style="color: #856404; margin: 0 0 10px 0; font-size: 14px;">WHAT HAPPENS NEXT?</h3>
                    <ul style="color: #856404; margin: 0; padding-left: 20px; font-size: 13px;">
                        <li>The partner will review your case</li>
                        <li>They may contact you for additional information</li>
                        <li>Keep this email for your records</li>
                        <li>If in immediate danger, contact emergency services</li>
                    </ul>
                </div>
            </td>
        </tr>
        
        <tr>
            <td style="background-color: #1a1a2e; padding: 20px; text-align: center;">
                <p style="color: #ffffff; margin: 0 0 5px 0; font-size: 13px; font-weight: bold;">
                    Project Imara - Protecting Women and Girls Online
                </p>
                <p style="color: #a0a0a0; margin: 0; font-size: 11px;">
                    "Imara" means "Strong" in Swahili. You are not alone.
                </p>
                <p style="color: #a0a0a0; margin: 8px 0 0 0; font-size: 10px;">
                    Sent: {timestamp}
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html
    
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
