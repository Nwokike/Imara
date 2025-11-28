import os
import logging
from typing import Optional, Dict, Any
from django.utils import timezone
from django.core.files.base import ContentFile

from cases.models import IncidentReport, EvidenceAsset
from directory.models import AuthorityContact
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
        reporter_email: Optional[str] = None
    ) -> Dict[str, Any]:
        incident = IncidentReport.objects.create(
            source=source,
            reporter_handle=reporter_handle,
            reporter_email=reporter_email,
            original_text=text
        )
        
        try:
            result = decision_engine.analyze_text(text)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            incident.detected_location = result.location
            incident.generate_chain_hash()
            incident.save()
            
            if result.should_report:
                dispatch_result = self._dispatch_to_authority(incident, result, text)
                return {
                    "success": True,
                    "action": "report",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "message": "Your report has been escalated to the appropriate authorities. Stay safe.",
                    "dispatched": dispatch_result.get("success", False)
                }
            else:
                return {
                    "success": True,
                    "action": "advise",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "advice": result.advice or self._get_default_advice(result.threat_type),
                    "message": "We've analyzed your report and have some advice for you."
                }
                
        except Exception as e:
            logger.error(f"Error processing text report: {e}")
            incident.action = "pending"
            incident.save()
            return {
                "success": False,
                "case_id": str(incident.case_id),
                "error": "We encountered an issue processing your report. Please try again.",
                "message": "If you feel in immediate danger, please contact local emergency services."
            }
    
    def process_image_report(
        self,
        image_file,
        source: str = "web",
        reporter_handle: Optional[str] = None,
        reporter_email: Optional[str] = None,
        additional_text: Optional[str] = None
    ) -> Dict[str, Any]:
        incident = IncidentReport.objects.create(
            source=source,
            reporter_handle=reporter_handle,
            reporter_email=reporter_email,
            original_text=additional_text
        )
        
        try:
            image_bytes = image_file.read()
            mime_type = getattr(image_file, 'content_type', 'image/jpeg')
            
            evidence = EvidenceAsset.objects.create(
                incident=incident,
                asset_type="image"
            )
            evidence.file.save(image_file.name, ContentFile(image_bytes))
            evidence.generate_hash()
            evidence.save()
            
            result = decision_engine.analyze_image_bytes(image_bytes, mime_type)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            incident.detected_location = result.location
            incident.extracted_text = result.extracted_text
            incident.generate_chain_hash()
            incident.save()
            
            evidence.derived_text = result.extracted_text
            evidence.save()
            
            evidence_text = result.extracted_text or additional_text or "Image evidence attached"
            
            if result.should_report:
                dispatch_result = self._dispatch_to_authority(incident, result, evidence_text)
                return {
                    "success": True,
                    "action": "report",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "extracted_text": result.extracted_text,
                    "message": "Your screenshot has been analyzed and reported to the appropriate authorities. Stay safe.",
                    "dispatched": dispatch_result.get("success", False)
                }
            else:
                return {
                    "success": True,
                    "action": "advise",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "extracted_text": result.extracted_text,
                    "advice": result.advice or self._get_default_advice(result.threat_type),
                    "message": "We've analyzed your screenshot and have some advice for you."
                }
                
        except Exception as e:
            logger.error(f"Error processing image report: {e}")
            incident.action = "pending"
            incident.save()
            return {
                "success": False,
                "case_id": str(incident.case_id),
                "error": "We encountered an issue processing your image. Please try again.",
                "message": "If you feel in immediate danger, please contact local emergency services."
            }
    
    def process_audio_report(
        self,
        audio_file,
        source: str = "web",
        reporter_handle: Optional[str] = None,
        reporter_email: Optional[str] = None
    ) -> Dict[str, Any]:
        incident = IncidentReport.objects.create(
            source=source,
            reporter_handle=reporter_handle,
            reporter_email=reporter_email
        )
        
        try:
            audio_bytes = audio_file.read()
            
            evidence = EvidenceAsset.objects.create(
                incident=incident,
                asset_type="audio"
            )
            evidence.file.save(audio_file.name, ContentFile(audio_bytes))
            evidence.generate_hash()
            evidence.save()
            
            temp_path = evidence.file.path
            result = decision_engine.analyze_audio(temp_path)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            incident.detected_location = result.location
            incident.transcribed_text = result.extracted_text
            incident.generate_chain_hash()
            incident.save()
            
            evidence.derived_text = result.extracted_text
            evidence.save()
            
            if result.should_report:
                dispatch_result = self._dispatch_to_authority(incident, result, result.extracted_text or "Voice note evidence")
                return {
                    "success": True,
                    "action": "report",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "transcribed_text": result.extracted_text,
                    "message": "Your voice note has been transcribed and reported to the appropriate authorities. Stay safe.",
                    "dispatched": dispatch_result.get("success", False)
                }
            else:
                return {
                    "success": True,
                    "action": "advise",
                    "case_id": str(incident.case_id),
                    "risk_score": result.risk_score,
                    "summary": result.summary,
                    "transcribed_text": result.extracted_text,
                    "advice": result.advice or self._get_default_advice(result.threat_type),
                    "message": "We've analyzed your voice note and have some advice for you."
                }
                
        except Exception as e:
            logger.error(f"Error processing audio report: {e}")
            incident.action = "pending"
            incident.save()
            return {
                "success": False,
                "case_id": str(incident.case_id),
                "error": "We encountered an issue processing your audio. Please try again.",
                "message": "If you feel in immediate danger, please contact local emergency services."
            }
    
    def _dispatch_to_authority(
        self,
        incident: IncidentReport,
        result: TriageResult,
        evidence_text: str
    ) -> Dict[str, Any]:
        if not brevo_dispatcher:
            logger.warning("Brevo dispatcher not configured, skipping email dispatch")
            return {"success": False, "error": "Email dispatcher not configured"}
        
        authority = AuthorityContact.find_by_location(result.location)
        
        if not authority:
            logger.warning(f"No authority found for location: {result.location}")
            return {"success": False, "error": "No authority contact found"}
        
        def on_dispatch_complete(dispatch_result):
            status = "sent" if dispatch_result.get("success") else "failed"
            error_msg = dispatch_result.get("error") if not dispatch_result.get("success") else None
            
            DispatchLog.objects.create(
                incident=incident,
                authority=authority,
                recipient_email=authority.email,
                subject=f"FORENSIC ALERT - Case #{str(incident.case_id)[:8].upper()}",
                status=status,
                brevo_message_id=dispatch_result.get("message_id"),
                error_message=error_msg,
                sent_at=timezone.now() if status == "sent" else None
            )
            
            if status == "sent":
                incident.dispatched_at = timezone.now()
                incident.dispatched_to = authority.email
                incident.save()
        
        brevo_dispatcher.send_async(
            recipient_email=authority.email,
            case_id=str(incident.case_id),
            evidence_text=evidence_text,
            risk_score=result.risk_score,
            threat_type=result.threat_type or "Unknown",
            location=result.location or "Unknown",
            chain_hash=incident.chain_hash or "",
            summary=result.summary,
            source=incident.get_source_display(),
            callback=on_dispatch_complete
        )
        
        return {"success": True, "recipient": authority.email}
    
    def _get_default_advice(self, threat_type: Optional[str]) -> str:
        advice_map = {
            "insult": "Block the person sending these messages. Don't engage - that's what they want. Remember, their words don't define you.",
            "harassment": "Document everything. Block the harasser on all platforms. Consider reporting to the platform's moderation team.",
            "stalking": "Change your privacy settings immediately. Don't share your location. Consider contacting local authorities if this continues.",
            "threat": "Take this seriously. Save all evidence. Contact local authorities immediately. Don't respond to the threat.",
            "doxing": "Contact the platforms where your info was shared to request removal. Change passwords and enable 2FA. Consider a police report.",
            "blackmail": "Don't pay or comply with demands. Save all evidence. Contact law enforcement immediately.",
        }
        
        default = "Block the person, document everything, and don't engage. If you feel unsafe, contact local authorities. You're not alone - support is available."
        
        return advice_map.get(threat_type, default) if threat_type else default


report_processor = ReportProcessor()
