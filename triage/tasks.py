"""
Asynchronous Agent Orchestration Tasks for Project Imara.
Utilizes Django 6 Native Tasks framework for 1GB RAM optimization.
"""
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.tasks import task
from .models import ChatMessage, ChatSession, UserFeedback

logger = logging.getLogger(__name__)

@task()
def process_telegram_update_task(data: dict):
    """
    Asynchronous Agent Orchestration for Telegram.
    Pipelines the message through specialized micro-agents.
    """
    from intake.webhook_service import TelegramProcessor
    from .decision_engine import decision_engine
    from django.db import close_old_connections
    
    try:
        close_old_connections()
        processor = TelegramProcessor()
        
        message = data.get('message')
        if not message: return
        
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        username = user.get('username') or user.get('first_name') or 'Anonymous'
        
        session = processor.get_or_create_session(chat_id, 'telegram', username)
        
        if session.is_cancelled():
            return

        text = message.get('text') or message.get('caption') or ""
        history = session.get_messages_for_llm(limit=10)
        
        # 1. Pipeline through Orchestrator (Chat Pipeline)
        result = decision_engine.chat_orchestration(text, history=history)
        
        # 2. Deliver Agent Response
        processor.send_result(chat_id, result, session)

    except Exception as e:
        logger.error(f"Telegram Orchestration Task failed: {e}")
    finally:
        close_old_connections()

@task()
def process_meta_event_task(event: dict, platform: str):
    """
    Asynchronous Agent Orchestration for Meta Platforms (Messenger/Instagram).
    """
    from intake.webhook_service import MetaProcessor
    from .decision_engine import decision_engine
    from django.db import close_old_connections
    
    try:
        close_old_connections()
        processor = MetaProcessor()
        
        sender_id = event.get('sender', {}).get('id')
        if not sender_id: return
        
        session = processor.get_or_create_session(sender_id, platform)
        
        if session.is_cancelled():
            return

        message = event.get('message', {})
        text = message.get('text') or ""
        history = session.get_messages_for_llm(limit=10)
        
        # 1. Pipeline through Orchestrator (Chat Pipeline)
        result = decision_engine.chat_orchestration(text, history=history)
        
        # 2. Deliver
        processor._send_meta_result(sender_id, result, session, platform)

    except Exception as e:
        logger.error(f"Meta Orchestration Task failed: {e}")
    finally:
        close_old_connections()

@task()
def triage_retention_cleanup_task():
    """
    Periodic retention cleanup for triage data (Native Django 6 Task).
    """
    msg_days = getattr(settings, "TRIAGE_MESSAGE_RETENTION_DAYS", 90)
    now = timezone.now()
    cutoff = now - timedelta(days=int(msg_days))

    deleted_msgs, _ = ChatMessage.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Triage retention cleanup: deleted {deleted_msgs} old messages.")

@task()
def process_web_report_task(incident_id: int):
    """
    Asynchronous forensic analysis for one-time web reports.
    Uses the 'web_orchestration' stateless pipeline.
    """
    from cases.models import IncidentReport
    from .decision_engine import decision_engine
    from intake.services import report_processor
    
    try:
        incident = IncidentReport.objects.get(pk=incident_id)
        
        # Run Web Batch Orchestration (Stateless)
        result = decision_engine.web_orchestration(
            text=incident.original_text,
            metadata={"source": "web", "case_id": str(incident.case_id)}
        )
        
        # Update incident with results
        incident.ai_analysis = result.to_dict()
        incident.risk_score = result.risk_score
        incident.action = result.action.lower()
        incident.detected_location = result.location
        incident.forensic_hash = result.forensic_hash
        incident.save()
        
        # Dispatch to partner if needed
        if result.should_report:
            report_processor._dispatch_to_partner(incident, result, incident.original_text)
            
    except Exception as e:
        logger.error(f"Web report task failed for incident {incident_id}: {e}")
