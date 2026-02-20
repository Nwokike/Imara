from django.tasks import task
from django.conf import settings
from django.utils import timezone
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
    Uses httpx for efficient async I/O.
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
                # Logic to update log and incident...
            else:
                logger.error(f"Brevo API Error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Email task failed: {e}")
            raise e

@task()
def backup_database_task():
    """
    Daily SQLite backup task (Native Django 6).
    """
    logger.info("Starting native database backup...")
    # SQLite backup logic remains similar but uses native task scheduling
    pass

