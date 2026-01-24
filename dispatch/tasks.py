from django_huey import task
import requests
from django.conf import settings
from django.utils import timezone
import logging
import json
import os
import boto3
import sqlite3
from datetime import datetime
from pathlib import Path
from huey import crontab
from django_huey import periodic_task

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

@task(queue='dispatch')
def send_email_task(payload, dispatch_log_id=None, incident_id=None):
    """
    Background task to send email via Brevo API.
    
    Args:
        payload: Email payload dict (sender, to, subject, htmlContent)
        dispatch_log_id: Optional DispatchLog ID to update with result
        incident_id: Optional IncidentReport ID (used if dispatch_log_id not provided)
    """
    api_key = getattr(settings, 'BREVO_API_KEY', None)
    if not api_key:
        logger.warning("BREVO_API_KEY not found in settings - email task skipped")
        if dispatch_log_id:
            _update_dispatch_log(dispatch_log_id, status='failed', error_message='Brevo API key not configured')
        return

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    try:
        response = requests.post(
            BREVO_API_URL, 
            headers=headers, 
            json=payload, 
            timeout=30
        )
        
        if response.status_code in [200, 201, 202]:
            result = response.json()
            message_id = result.get('messageId')
            logger.info(f"Email sent successfully via Huey. Message ID: {message_id}")
            
            if dispatch_log_id:
                _update_dispatch_log(
                    dispatch_log_id, 
                    status='sent', 
                    brevo_message_id=message_id,
                    sent_at=timezone.now()
                )
                
                if incident_id:
                    from cases.models import IncidentReport
                    try:
                        incident = IncidentReport.objects.get(pk=incident_id)
                        recipient_email = payload.get('to', [{}])[0].get('email', '')
                        IncidentReport.objects.filter(pk=incident_id).update(
                            dispatched_at=timezone.now(),
                            dispatched_to=recipient_email
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update incident dispatch status: {e}")
        else:
            error_text = response.text
            logger.error(f"Brevo API Error: {response.status_code} - {error_text}")
            if dispatch_log_id:
                _update_dispatch_log(
                    dispatch_log_id, 
                    status='failed', 
                    error_message=f"Brevo API error {response.status_code}: {error_text[:500]}"
                )
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error executing send_email_task: {error_msg}")
        if dispatch_log_id:
            _update_dispatch_log(dispatch_log_id, status='failed', error_message=error_msg[:500])
        raise e


def _update_dispatch_log(dispatch_log_id, status, brevo_message_id=None, error_message=None, sent_at=None):
    """Helper to update DispatchLog entry"""
    try:
        from dispatch.models import DispatchLog
        update_kwargs = {'status': status}
        if brevo_message_id:
            update_kwargs['brevo_message_id'] = brevo_message_id
        if error_message:
            update_kwargs['error_message'] = error_message
        if sent_at:
            update_kwargs['sent_at'] = sent_at
        DispatchLog.objects.filter(pk=dispatch_log_id).update(**update_kwargs)
    except Exception as e:
        logger.error(f"Failed to update DispatchLog {dispatch_log_id}: {e}")

@periodic_task(crontab(hour=3, minute=0))
def backup_database_task():
    """
    Periodic task to backup SQLite database to Cloudflare R2.
    Runs every day at 3:00 AM.
    Keeps only the last 3 backups in the bucket.
    
    NOTE: This task only runs for SQLite databases. For Postgres deployments,
    use a separate pg_dump-based backup process.
    """
    db_vendor = settings.DATABASES['default'].get('ENGINE', '')
    
    if 'sqlite' not in db_vendor.lower():
        logger.info(f"Database backup skipped - not using SQLite (vendor: {db_vendor}). "
                   "Use pg_dump or equivalent for Postgres backups.")
        return
    
    logger.info("Starting SQLite database backup task...")
    
    db_path = settings.DATABASES['default']['NAME']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    local_filename = f"imara_backup_{timestamp}.sqlite3"
    backup_path = settings.BASE_DIR / local_filename
    r2_key = f"db-backups/{local_filename}"
    
    bucket_name = os.environ.get('R2_BACKUP_BUCKET_NAME', 'imara-backups')
    endpoint_url = os.environ.get('R2_ENDPOINT_URL')
    access_key = os.environ.get('R2_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
    
    if not (bucket_name and endpoint_url and access_key and secret_key):
        logger.error("R2 backup configuration missing - backup skipped")
        return

    try:
        # 1. Create local backup using SQLite API (safe during runtime)
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        logger.info(f"Local backup created: {backup_path}")
        
        # 2. Upload to R2 with dedicated prefix
        s3 = boto3.client('s3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        s3.upload_file(str(backup_path), bucket_name, r2_key)
        logger.info(f"Backup uploaded to R2: {r2_key}")
        
        # 3. Cleanup local file
        os.remove(backup_path)
        
        # 4. Enforce Retention Policy (Keep last 3, scoped to db-backups/ prefix)
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='db-backups/')
        if 'Contents' in response:
            backups = sorted(response['Contents'], key=lambda x: x['LastModified'])
            
            # If we have more than 3, delete the oldest ones
            while len(backups) > 3:
                oldest = backups.pop(0)
                s3.delete_object(Bucket=bucket_name, Key=oldest['Key'])
                logger.info(f"Deleted old backup: {oldest['Key']}")
                
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        # Clean up local file if it exists
        if os.path.exists(backup_path):
            os.remove(backup_path)
