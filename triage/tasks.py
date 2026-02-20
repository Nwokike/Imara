import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django_huey import periodic_task
from huey import crontab

from .models import ChatMessage, ChatSession, UserFeedback
from django_huey import task, periodic_task

logger = logging.getLogger(__name__)

@task(queue='dispatch')
def process_telegram_update_task(data):
    """
    Asynchronous Agent Orchestration for Telegram.
    Pipelines the message through specialized micro-agents.
    """
    from intake.webhook_service import TelegramProcessor
    from .decision_engine import decision_engine
    from .agents.base import ContextBundle
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
        
        # Check if cancelled
        if session.is_cancelled():
            logger.info(f"Task skipped for {chat_id} - session cancelled")
            return

        text = message.get('text') or message.get('caption') or ""
        history = session.get_messages_for_llm(limit=10)
        
        # 1. Pipeline through Orchestrator
        # Note: Image URL handling would happen here if present
        result = decision_engine.process_incident(text, history=history)
        
        # 2. Persist Forensic Evidence
        if result.forensic_hash:
            # Update incident report if we have a case_id (to be integrated)
            pass

        # 3. Deliver Agent Response
        if result.needs_location:
            from utils.safety import get_localized_location_prompt
            msg = get_localized_location_prompt(session.language_preference)
            session.awaiting_location = True
            session.save()
            processor.send_message(chat_id, msg)
        else:
            processor.send_result(chat_id, result.to_dict(), session)

    except Exception as e:
        logger.error(f"Telegram Orchestration Task failed: {e}")
    finally:
        close_old_connections()

@task(queue='dispatch')
def process_meta_event_task(event, platform):
    """
    Asynchronous Agent Orchestration for Meta Platforms.
    """
    from intake.webhook_service import MetaProcessor
    from .decision_engine import decision_engine
    from .agents.base import ContextBundle
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
        
        # Orchestrate
        result = decision_engine.process_incident(text, history=history)
        
        # Deliver
        processor._send_result(sender_id, result.to_dict(), session, platform)

    except Exception as e:
        logger.error(f"Meta Orchestration Task failed: {e}")
    finally:
        close_old_connections()

@periodic_task(crontab(hour=4, minute=15))
def triage_retention_cleanup_task():
    """
    Periodic retention cleanup for triage data.

    Keeps the database small and fast on 1GB VMs by pruning:
    - old chat messages
    - stale sessions without recent activity
    - old feedback records
    """
    msg_days = getattr(settings, "TRIAGE_MESSAGE_RETENTION_DAYS", 90)
    session_days = getattr(settings, "TRIAGE_SESSION_RETENTION_DAYS", 90)
    feedback_days = getattr(settings, "TRIAGE_FEEDBACK_RETENTION_DAYS", 365)

    now = timezone.now()
    msg_cutoff = now - timedelta(days=int(msg_days))
    session_cutoff = now - timedelta(days=int(session_days))
    feedback_cutoff = now - timedelta(days=int(feedback_days))

    deleted_msgs, _ = ChatMessage.objects.filter(created_at__lt=msg_cutoff).delete()
    deleted_feedback, _ = UserFeedback.objects.filter(created_at__lt=feedback_cutoff).delete()

    # Delete sessions that are stale AND have no recent messages.
    # (Sessions with messages are effectively cleaned as messages are pruned.)
    stale_sessions = ChatSession.objects.filter(updated_at__lt=session_cutoff)
    deleted_sessions = 0
    for s in stale_sessions.only("id"):
        # If there are no remaining messages for this session, delete it.
        if not ChatMessage.objects.filter(session_id=s.id).exists():
            s.delete()
            deleted_sessions += 1

    logger.info(
        "Triage retention cleanup completed. "
        f"deleted_messages={deleted_msgs} deleted_feedback={deleted_feedback} deleted_sessions={deleted_sessions}"
    )

