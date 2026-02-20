import os
import logging
import hashlib
from typing import Optional, Dict, Any
from io import BytesIO
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile

from cases.models import IncidentReport, EvidenceAsset
from partners.models import PartnerOrganization
from triage.decision_engine import decision_engine, TriageResult
from dispatch.service import brevo_dispatcher
from dispatch.models import DispatchLog

logger = logging.getLogger(__name__)


class ReportProcessor:
    def process_text_report(
        self,
        text: str,
        source: str = "web",
        reporter_handle: Optional[str] = None,
        reporter_email: Optional[str] = None,
        reporter_name: Optional[str] = None,
        contact_preference: Optional[str] = None,
        perpetrator_info: Optional[str] = None,
        location_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        incident = IncidentReport.objects.create(
            source=source,
            reporter_handle=reporter_handle,
            reporter_email=reporter_email,
            reporter_name=reporter_name,
            contact_preference=contact_preference or ("email" if reporter_email else None),
            perpetrator_info=perpetrator_info,
            original_text=text,
            detected_location=location_hint
        )
        
        text_evidence = EvidenceAsset.objects.create(
            incident=incident,
            asset_type="text",
            derived_text=text
        )
        text_evidence.sha256_digest = hashlib.sha256(text.encode()).hexdigest()
        text_evidence.save()
        
        try:
            result = decision_engine.analyze_text(text)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            final_location = location_hint or result.location
            incident.detected_location = final_location
            result.location = final_location
            incident.save()
            
            incident.generate_chain_hash()
            incident.save()
            
            if result.should_report:
                dispatch_result = self._dispatch_to_partner(incident, result, text)
                
                # FALLBACK: If dispatch failed (e.g. invalid location), ASK USER.
                if not dispatch_result.get("success") and dispatch_result.get("error") == "No partner organization found":
                     return {
                        "success": True,
                        "action": "ask_location",
                        "case_id": str(incident.case_id),
                        "risk_score": result.risk_score,
                        "summary": result.summary,
                        "message": "I detected a location but couldn't connect you to a partner there. Please tell me your **City and Country** explicitly."
                    }
                
                if reporter_email and dispatch_result.get("success"):
                    self._send_user_confirmation(
                        reporter_email=reporter_email,
                        case_id=str(incident.case_id),
                        partner_name=dispatch_result.get("partner_name"),
                        partner_email=dispatch_result.get("partner_email"),
                        risk_score=result.risk_score,
                        summary=result.summary,
                        location=result.location
                    )
                
                return {
                    "success": True,
                    "action": "report",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "message": "Your report has been escalated to the appropriate support partner. Stay safe.",
                    "dispatched": dispatch_result.get("success", False),
                    "partner_name": dispatch_result.get("partner_name"),
                    "partner_email": dispatch_result.get("partner_email")
                }
            elif result.action.upper() == 'ASK_LOCATION':
                return {
                    "success": True,
                    "action": "ask_location",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "message": "We need your location to help you further."
                }
            else:
                advice = result.advice or self._get_default_advice(result.threat_type)
                return {
                    "success": True,
                    "action": "advise",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "advice": advice,
                    "message": "We've analyzed your report and have some advice for you."
                }
                
        except Exception as e:
            logger.error(f"Error processing text report: {e}")
            incident.action = "pending"
            incident.save()
            return {
                "success": False,
                "action": "error",
                "case_id": str(incident.case_id),
                "risk_score": 0,
                "summary": "Processing error",
                "error": "We encountered an issue processing your report. Please try again.",
                "message": "If you feel in immediate danger, please contact local emergency services.",
                "advice": "Please try again or contact local emergency services if you feel unsafe."
            }
    
    def process_image_report(
        self,
        image_file,
        source: str = "web",
        reporter_handle: Optional[str] = None,
        reporter_email: Optional[str] = None,
        reporter_name: Optional[str] = None,
        contact_preference: Optional[str] = None,
        perpetrator_info: Optional[str] = None,
        additional_text: Optional[str] = None,
        location_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        incident = IncidentReport.objects.create(
            source=source,
            reporter_handle=reporter_handle,
            reporter_email=reporter_email,
            reporter_name=reporter_name,
            contact_preference=contact_preference or ("email" if reporter_email else None),
            perpetrator_info=perpetrator_info,
            original_text=additional_text,
            detected_location=location_hint
        )
        
        try:
            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            
            # Calculate hash via streaming (low memory usage)
            hasher = hashlib.sha256()
            for chunk in image_file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()
            
            image_file.seek(0)
            
            file_name = getattr(image_file, 'name', 'screenshot.jpg') or 'screenshot.jpg'
            
            # Determine mime type
            mime_type = getattr(image_file, 'content_type', None)
            if not mime_type:
                ext = file_name.lower().split('.')[-1] if '.' in file_name else 'jpg'
                mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
                mime_type = mime_map.get(ext, 'image/jpeg')
            
            evidence = EvidenceAsset.objects.create(
                incident=incident,
                asset_type="image"
            )
            # Django save() streams from the file object
            evidence.file.save(file_name, image_file)
            evidence.sha256_digest = file_hash
            evidence.save()
            
            # Analyze using the saved file object (streams from storage/disk)
            with evidence.file.open('rb') as f:
                result = decision_engine.analyze_image(f, mime_type)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            final_location = location_hint or result.location
            incident.detected_location = final_location
            result.location = final_location
            incident.extracted_text = result.extracted_text
            incident.save()
            
            incident.generate_chain_hash()
            incident.save()
            
            evidence.derived_text = result.extracted_text
            evidence.save()
            
            evidence_text = result.extracted_text or additional_text or "Image evidence attached"
            
            if result.should_report:
                dispatch_result = self._dispatch_to_partner(incident, result, evidence_text)
                
                # FALLBACK: If dispatch failed (e.g. invalid location), ASK USER.
                if not dispatch_result.get("success") and dispatch_result.get("error") == "No partner organization found":
                     return {
                        "success": True,
                        "action": "ask_location",
                        "case_id": str(incident.case_id),
                        "risk_score": result.risk_score,
                        "summary": result.summary,
                        "extracted_text": result.extracted_text,
                        "message": "I detected a location but couldn't connect you to a partner there. Please tell me your **City and Country** explicitly."
                    }
                
                if reporter_email and dispatch_result.get("success"):
                    self._send_user_confirmation(
                        reporter_email=reporter_email,
                        case_id=str(incident.case_id),
                        partner_name=dispatch_result.get("partner_name"),
                        partner_email=dispatch_result.get("partner_email"),
                        risk_score=result.risk_score,
                        summary=result.summary,
                        location=result.location
                    )
                
                return {
                    "success": True,
                    "action": "report",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "extracted_text": result.extracted_text,
                    # ... extracted_text ...
                    "message": "Your screenshot has been analyzed and escalated to the appropriate support partner. Stay safe.",
                    "dispatched": dispatch_result.get("success", False),
                    "partner_name": dispatch_result.get("partner_name"),
                    "partner_email": dispatch_result.get("partner_email")
                }
            elif result.action.upper() == 'ASK_LOCATION':
                return {
                    "success": True,
                    "action": "ask_location",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "extracted_text": result.extracted_text,
                    "message": "We need your location to help you further."
                }
            else:
                advice = result.advice or self._get_default_advice(result.threat_type)
                return {
                    "success": True,
                    "action": "advise",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "extracted_text": result.extracted_text,
                    "advice": advice,
                    "message": "We've analyzed your screenshot and have some advice for you."
                }
                
        except Exception as e:
            logger.error(f"Error processing image report: {e}")
            incident.action = "pending"
            incident.save()
            return {
                "success": False,
                "action": "error",
                "case_id": str(incident.case_id),
                "risk_score": 0,
                "summary": "Processing error",
                "error": "We encountered an issue processing your image. Please try again.",
                "message": "If you feel in immediate danger, please contact local emergency services.",
                "advice": "Please try again or contact local emergency services if you feel unsafe."
            }
    
    def process_audio_report(
        self,
        audio_file,
        source: str = "web",
        reporter_handle: Optional[str] = None,
        reporter_email: Optional[str] = None,
        reporter_name: Optional[str] = None,
        contact_preference: Optional[str] = None,
        perpetrator_info: Optional[str] = None,
        location_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        incident = IncidentReport.objects.create(
            source=source,
            reporter_handle=reporter_handle,
            reporter_email=reporter_email,
            reporter_name=reporter_name,
            contact_preference=contact_preference or ("email" if reporter_email else None),
            perpetrator_info=perpetrator_info,
            detected_location=location_hint
        )
        
        try:
            if hasattr(audio_file, 'seek'):
                audio_file.seek(0)
                
            # Stream hash calculation
            hasher = hashlib.sha256()
            for chunk in audio_file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()
            
            audio_file.seek(0)
            
            file_name = getattr(audio_file, 'name', 'voice_note.ogg') or 'voice_note.ogg'
            
            evidence = EvidenceAsset.objects.create(
                incident=incident,
                asset_type="audio"
            )
            evidence.file.save(file_name, audio_file)
            evidence.sha256_digest = file_hash
            evidence.save()
            
            with evidence.file.open('rb') as f:
                result = decision_engine.analyze_audio(f)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            final_location = location_hint or result.location
            incident.detected_location = final_location
            result.location = final_location
            incident.transcribed_text = result.extracted_text
            incident.save()
            
            incident.generate_chain_hash()
            incident.save()
            
            evidence.derived_text = result.extracted_text
            evidence.save()
            
            if result.should_report:
                dispatch_result = self._dispatch_to_partner(incident, result, result.extracted_text or "Voice note evidence")
                
                # FALLBACK: If dispatch failed (e.g. invalid location), ASK USER.
                if not dispatch_result.get("success") and dispatch_result.get("error") == "No partner organization found":
                     return {
                        "success": True,
                        "action": "ask_location",
                        "case_id": str(incident.case_id),
                        "risk_score": result.risk_score,
                        "summary": result.summary,
                        "transcribed_text": result.extracted_text,
                        "extracted_text": result.extracted_text,
                        "message": "I detected a location but couldn't connect you to a partner there. Please tell me your **City and Country** explicitly."
                    }
                
                if reporter_email and dispatch_result.get("success"):
                    self._send_user_confirmation(
                        reporter_email=reporter_email,
                        case_id=str(incident.case_id),
                        partner_name=dispatch_result.get("partner_name"),
                        partner_email=dispatch_result.get("partner_email"),
                        risk_score=result.risk_score,
                        summary=result.summary,
                        location=result.location
                    )
                
                return {
                    "success": True,
                    "action": "report",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "transcribed_text": result.extracted_text,
                    "extracted_text": result.extracted_text,
                    "message": "Your voice note has been transcribed and escalated to the appropriate support partner. Stay safe.",
                    "dispatched": dispatch_result.get("success", False),
                    "partner_name": dispatch_result.get("partner_name"),
                    "partner_email": dispatch_result.get("partner_email")
                }
            elif result.action.upper() == 'ASK_LOCATION':
                return {
                    "success": True,
                    "action": "ask_location",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "transcribed_text": result.extracted_text,
                    "extracted_text": result.extracted_text,
                    "message": "We need your location to help you further."
                }
            else:
                advice = result.advice or self._get_default_advice(result.threat_type)
                return {
                    "success": True,
                    "action": "advise",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "transcribed_text": result.extracted_text,
                    "extracted_text": result.extracted_text,
                    "advice": advice,
                    "message": "We've analyzed your voice note and have some advice for you."
                }
                
        except Exception as e:
            logger.error(f"Error processing audio report: {e}")
            incident.action = "pending"
            incident.save()
            return {
                "success": False,
                "action": "error",
                "case_id": str(incident.case_id),
                "risk_score": 0,
                "summary": "Processing error",
                "error": "We encountered an issue processing your audio. Please try again.",
                "message": "If you feel in immediate danger, please contact local emergency services.",
                "advice": "Please try again or contact local emergency services if you feel unsafe."
            }
    
    def _dispatch_to_partner(
        self,
        incident: IncidentReport,
        result: TriageResult,
        evidence_text: str
    ) -> Dict[str, Any]:
        if not brevo_dispatcher or not brevo_dispatcher.is_available:
            logger.warning("Brevo dispatcher not configured, skipping email dispatch")
            return {"success": False, "error": "Email dispatcher not configured"}
        
        partner = PartnerOrganization.find_by_location(result.location)
        
        if not partner:
            logger.warning(f"No partner organization found for location: {result.location}")
            return {"success": False, "error": "No partner organization found"}
        
        # Update incident with assigned partner and jurisdiction
        incident.assigned_partner = partner
        incident.jurisdiction = partner.jurisdiction
        incident.save()
        
        # Create DispatchLog entry with pending status before enqueueing
        dispatch_log = DispatchLog.objects.create(
            incident=incident,
            recipient_email=partner.contact_email,
            subject=f"FORENSIC ALERT - Case #{str(incident.case_id)[:8].upper()}",
            status='pending'
        )

        # Include structured contact/context for partner action (if available)
        evidence_lines = [evidence_text or ""]
        if incident.reporter_name:
            evidence_lines.append(f"\nReporter Name: {incident.reporter_name}")
        if incident.reporter_handle:
            evidence_lines.append(f"Reporter Handle: {incident.reporter_handle}")
        if incident.contact_preference:
            evidence_lines.append(f"Contact Preference: {incident.contact_preference}")
        if incident.reporter_email:
            evidence_lines.append(f"Reporter Email: {incident.reporter_email}")
        if incident.perpetrator_info:
            evidence_lines.append(f"Perpetrator Info: {incident.perpetrator_info}")

        dispatch_evidence_text = "\n".join([l for l in evidence_lines if l is not None])
        
        brevo_dispatcher.send_async(
            recipient_email=partner.contact_email,
            case_id=str(incident.case_id),
            evidence_text=dispatch_evidence_text,
            risk_score=result.risk_score,
            threat_type=result.threat_type or "Unknown",
            location=result.location or "Unknown",
            chain_hash=incident.chain_hash or "",
            summary=result.summary,
            source=incident.get_source_display(),
            dispatch_log_id=dispatch_log.pk,
            incident_id=incident.pk
        )

        # Notify Admin (Project Imara HQ) of the escalation
        from dispatch.tasks import send_email_task
        admin_subject = f"ADMIN ALERT: High Risk Case Escalated #{str(incident.case_id)[:8]}"
        admin_html = f"""
        <h3>High Risk Case Escalated</h3>
        <p><strong>Case ID:</strong> {str(incident.case_id)}</p>
        <p><strong>Risk Score:</strong> {result.risk_score}/10</p>
        <p><strong>Partner:</strong> {partner.name} ({partner.contact_email})</p>
        <p><strong>Location:</strong> {result.location}</p>
        <p><strong>Summary:</strong> {result.summary}</p>
        <hr>
        <p>Check Django Admin for full details.</p>
        """
        
        admin_payload = {
            "sender": {"name": "Imara System", "email": settings.BREVO_SENDER_EMAIL},
            "to": [{"email": settings.ADMIN_NOTIFICATION_EMAIL}],
            "subject": admin_subject,
            "htmlContent": admin_html
        }
        send_email_task(admin_payload)
        
        return {
            "success": True, 
            "recipient": partner.contact_email,
            "partner_name": partner.name,
            "partner_email": partner.contact_email
        }
    
    def _send_user_confirmation(
        self,
        reporter_email: str,
        case_id: str,
        partner_name: Optional[str],
        partner_email: Optional[str],
        risk_score: int,
        summary: str,
        location: Optional[str]
    ) -> None:
        if not brevo_dispatcher or not brevo_dispatcher.is_available:
            logger.warning("Brevo dispatcher not available for user confirmation")
            return
        
        try:
            brevo_dispatcher.send_user_confirmation_async(
                user_email=reporter_email,
                case_id=case_id,
                partner_name=partner_name or "Support Partner",
                partner_email=partner_email or "",
                risk_score=risk_score,
                summary=summary,
                location=location or "Unknown"
            )
            logger.info(f"User confirmation email queued for {reporter_email}")
        except Exception as e:
            logger.error(f"Failed to send user confirmation: {e}")
    
    def _get_default_advice(self, threat_type: Optional[str]) -> str:
        advice_map = {
            "insult": "Block the person sending these messages. Don't engage - that's what they want. Remember, their words don't define you.",
            "harassment": "Document everything. Block the harasser on all platforms. Consider reporting to the platform's moderation team.",
            "stalking": "Change your privacy settings immediately. Don't share your location. Consider contacting local emergency services if you feel unsafe or if this continues.",
            "threat": "Take this seriously. Save all evidence. Contact local emergency services immediately if you are in danger. Don't respond to the threat.",
            "doxing": "Contact the platforms where your info was shared to request removal. Change passwords and enable 2FA. Consider a police report.",
            "blackmail": "Don't pay or comply with demands. Save all evidence. Contact law enforcement immediately.",
        }
        
        default = "Block the person, document everything, and don't engage. If you feel unsafe, contact local emergency services. You're not alone - support is available."
        
        return advice_map.get(threat_type, default) if threat_type else default


    def update_location_and_dispatch(self, case_id: str, location: str) -> Dict[str, Any]:
        """Update incident with location and retry dispatch."""
        try:
            incident = IncidentReport.objects.get(case_id=case_id)
            incident.detected_location = location
            incident.action = 'report'
            incident.save()
            
            # Reconstruct result object for dispatch
            class MockResult:
                def __init__(self, incident, location):
                    self.risk_score = incident.risk_score
                    self.threat_type = (incident.ai_analysis or {}).get('threat_type')
                    self.location = location
                    self.summary = (incident.ai_analysis or {}).get('summary', 'Report upgraded with location')
            
            result = MockResult(incident, location)
            
            # Get evidence text (prefer derived text, then original)
            evidence_text = ""
            evidence = incident.evidence_assets.first()
            if evidence:
                evidence_text = evidence.derived_text or incident.original_text or "Evidence attached"
            else:
                evidence_text = incident.original_text or "Report evidence"
            
            dispatch_result = self._dispatch_to_partner(incident, result, evidence_text)
            
            if not dispatch_result.get("success"):
                return {
                    "success": False, 
                    "error": dispatch_result.get("error", "Dispatch failed"),
                    "partner_name": None
                }
            
            if incident.reporter_email and dispatch_result.get("success"):
                self._send_user_confirmation(
                    reporter_email=incident.reporter_email,
                    case_id=str(incident.case_id),
                    partner_name=dispatch_result.get("partner_name"),
                    partner_email=dispatch_result.get("partner_email"),
                    risk_score=result.risk_score,
                    summary=result.summary,
                    location=result.location
                )
            
            return {
                "success": True,
                "action": "report",
                "case_id": str(incident.case_id),
                "message": "Your report has been updated with location and escalated.",
                "partner_name": dispatch_result.get("partner_name")
            }
            
        except IncidentReport.DoesNotExist:
            return {"success": False, "error": "Case not found"}
        except Exception as e:
            logger.error(f"Error updating location dispatch: {e}")
            return {"success": False, "error": str(e)}


report_processor = ReportProcessor()
