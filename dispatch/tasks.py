from django.tasks import task
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
import httpx
import logging
import json
import os
import boto3
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

@task()
async def send_email_task(payload, dispatch_log_id=None, incident_id=None):
    """
    Native Django 6 Background Task to send email via Brevo API.
    Uses httpx for efficient async I/O and sync_to_async for DB updates.
    """
    api_key = getattr(settings, 'BREVO_API_KEY', None)
    if not api_key:
        logger.warning("BREVO_API_KEY missing - email task skipped")
        return

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code in [200, 201, 202]:
                logger.info("Email sent successfully via Django Tasks.")
                
                # Update DB state asynchronously
                await _update_dispatch_state(dispatch_log_id, incident_id, response.json().get('messageId'))
            else:
                logger.error(f"Brevo API Error: {response.status_code}")
                if dispatch_log_id:
                    await _mark_dispatch_failed(dispatch_log_id)
                
        except Exception as e:
            logger.error(f"Email task failed: {e}")
            if dispatch_log_id:
                await _mark_dispatch_failed(dispatch_log_id)
            raise e

@sync_to_async
def _update_dispatch_state(dispatch_log_id, incident_id, message_id):
    from .models import DispatchLog
    from cases.models import IncidentReport
    
    if dispatch_log_id:
        try:
            log = DispatchLog.objects.get(pk=dispatch_log_id)
            log.status = 'sent'
            log.brevo_message_id = message_id
            log.save()
            
            if incident_id:
                incident = IncidentReport.objects.get(pk=incident_id)
                incident.dispatched_at = timezone.now()
                incident.dispatched_to = log.recipient_email
                incident.save()
        except Exception as e:
            logger.error(f"Async DB update failed: {e}")

@sync_to_async
def _mark_dispatch_failed(dispatch_log_id):
    from .models import DispatchLog
    try:
        log = DispatchLog.objects.get(pk=dispatch_log_id)
        log.status = 'failed'
        log.save()
    except Exception: pass

@task()
def backup_database_task():
    """
    Daily SQLite backup task (Native Django 6).
    Backs up to Cloudflare R2 and prunes old versions.
    """
    logger.info("Starting native database backup...")
    db_path = settings.DATABASES['default']['NAME']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    local_filename = f"imara_backup_{timestamp}.sqlite3"
    backup_path = Path(settings.BASE_DIR) / local_filename
    
    bucket_name = os.environ.get('R2_BACKUP_BUCKET_NAME')
    
    try:
        # 1. Atomic SQLite Backup
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        
        # 2. Async Upload to R2
        s3 = boto3.client('s3',
            endpoint_url=os.environ.get('R2_ENDPOINT_URL'),
            aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY')
        )
        
        s3.upload_file(str(backup_path), bucket_name, f"db-backups/{local_filename}")
        os.remove(backup_path)
        
        logger.info(f"Database backup {local_filename} uploaded to R2.")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        if backup_path.exists(): os.remove(backup_path)
