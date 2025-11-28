import os
import logging
import hashlib
from typing import Optional, Dict, Any
from io import BytesIO
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
            incident.detected_location = result.location
            incident.save()
            
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
                "advice": "Please try again or contact local authorities if you feel unsafe."
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
            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            image_bytes = image_file.read()
            
            file_name = getattr(image_file, 'name', 'screenshot.jpg')
            if not file_name:
                file_name = 'screenshot.jpg'
            
            mime_type = getattr(image_file, 'content_type', None)
            if not mime_type:
                ext = file_name.lower().split('.')[-1] if '.' in file_name else 'jpg'
                mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
                mime_type = mime_map.get(ext, 'image/jpeg')
            
            evidence = EvidenceAsset.objects.create(
                incident=incident,
                asset_type="image"
            )
            evidence.file.save(file_name, ContentFile(image_bytes))
            evidence.sha256_digest = hashlib.sha256(image_bytes).hexdigest()
            evidence.save()
            
            result = decision_engine.analyze_image_bytes(image_bytes, mime_type)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            incident.detected_location = result.location
            incident.extracted_text = result.extracted_text
            incident.save()
            
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
                "advice": "Please try again or contact local authorities if you feel unsafe."
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
            if hasattr(audio_file, 'seek'):
                audio_file.seek(0)
            audio_bytes = audio_file.read()
            
            file_name = getattr(audio_file, 'name', 'voice_note.ogg')
            if not file_name:
                file_name = 'voice_note.ogg'
            
            evidence = EvidenceAsset.objects.create(
                incident=incident,
                asset_type="audio"
            )
            evidence.file.save(file_name, ContentFile(audio_bytes))
            evidence.sha256_digest = hashlib.sha256(audio_bytes).hexdigest()
            evidence.save()
            
            audio_path = evidence.file.path
            result = decision_engine.analyze_audio(audio_path)
            
            incident.ai_analysis = result.to_dict()
            incident.risk_score = result.risk_score
            incident.action = result.action.lower()
            incident.detected_location = result.location
            incident.transcribed_text = result.extracted_text
            incident.save()
            
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
                    "extracted_text": result.extracted_text,
                    "message": "Your voice note has been transcribed and reported to the appropriate authorities. Stay safe.",
                    "dispatched": dispatch_result.get("success", False)
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
                "advice": "Please try again or contact local authorities if you feel unsafe."
            }
    
    def _dispatch_to_authority(
        self,
        incident: IncidentReport,
        result: TriageResult,
        evidence_text: str
    ) -> Dict[str, Any]:
        if not brevo_dispatcher or not brevo_dispatcher.is_available:
            logger.warning("Brevo dispatcher not configured, skipping email dispatch")
            return {"success": False, "error": "Email dispatcher not configured"}
        
        authority = AuthorityContact.find_by_location(result.location)
        
        if not authority:
            logger.warning(f"No authority found for location: {result.location}")
            return {"success": False, "error": "No authority contact found"}
        
        def on_dispatch_complete(dispatch_result):
            try:
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
                    IncidentReport.objects.filter(pk=incident.pk).update(
                        dispatched_at=timezone.now(),
                        dispatched_to=authority.email
                    )
                    logger.info(f"Dispatch completed for case {incident.case_id} to {authority.email}")
                else:
                    logger.error(f"Dispatch failed for case {incident.case_id}: {error_msg}")
                    
            except Exception as e:
                logger.error(f"Error in dispatch callback: {e}")
        
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
