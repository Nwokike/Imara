from django_huey import task
import requests
from django.conf import settings
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
def send_email_task(payload):
    """
    Background task to send email via Brevo API.
    Payload must contain: sender, to, subject, htmlContent.
    """
    api_key = getattr(settings, 'BREVO_API_KEY', None)
    if not api_key:
        logger.warning("BREVO_API_KEY not found in settings - email task skipped")
        return

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    try:
        # payload is a dict, requests.post will jsonify it
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
        else:
            logger.error(f"Brevo API Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Error executing send_email_task: {e}")
        # Huey will auto-retry if configured, or we can raise e to retry
        raise e

@periodic_task(crontab(hour=3, minute=0))
def backup_database_task():
    """
    Periodic task to backup SQLite database to Cloudflare R2.
    Runs every day at 3:00 AM.
    Keeps only the last 3 backups in the bucket.
    """
    logger.info("Starting database backup task...")
    
    db_path = settings.DATABASES['default']['NAME']
    backup_filename = f"imara_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
    backup_path = settings.BASE_DIR / backup_filename
    
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
        
        # 2. Upload to R2
        s3 = boto3.client('s3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        s3.upload_file(str(backup_path), bucket_name, backup_filename)
        logger.info(f"Backup uploaded to R2: {backup_filename}")
        
        # 3. Cleanup local file
        os.remove(backup_path)
        
        # 4. Enforce Retention Policy (Keep last 3)
        response = s3.list_objects_v2(Bucket=bucket_name)
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
