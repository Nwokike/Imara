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
    """Async processing of Telegram updates via persistent queue."""
    try:
        from intake.webhook_service import TelegramProcessor
        from django.db import close_old_connections
        close_old_connections()
        
        processor = TelegramProcessor()
        processor.process_update(data)
    except Exception as e:
        logger.error(f"Telegram task failed: {e}")
    finally:
        from django.db import close_old_connections
        close_old_connections()

@task(queue='dispatch')
def process_meta_event_task(event, platform):
    """Async processing of Meta (Messenger/Instagram) events via persistent queue."""
    try:
        from intake.webhook_service import MetaProcessor
        from django.db import close_old_connections
        close_old_connections()
        
        processor = MetaProcessor()
        processor.handle_messaging_event(event, platform)
    except Exception as e:
        logger.error(f"Meta task failed: {e}")
    finally:
        from django.db import close_old_connections
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

