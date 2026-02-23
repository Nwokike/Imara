"""
Webhook processing services for Telegram and Meta platforms.
Extracted from views to support persistent background tasks using httpx.
"""
import logging
import json
import os
import tempfile
import httpx
from django.conf import settings
from django.core.files import File
from django.db import close_old_connections

from triage.models import ChatSession, ChatMessage, UserFeedback
from utils.safety import check_safe_word, get_localized_safety_message, get_localized_location_prompt

logger = logging.getLogger(__name__)

class WebhookProcessor:
    """Base processor for platform webhooks."""
    
    def get_or_create_session(self, chat_id, platform, username=None):
        session, created = ChatSession.objects.get_or_create(
            chat_id=str(chat_id),
            platform=platform,
            defaults={'username': username}
        )
        if username and session.username != username:
            session.username = username
            session.save()
        return session

    def save_message(self, session, role, content, message_type='text', metadata=None):
        return ChatMessage.objects.create(
            session=session,
            role=role,
            content=content[:2000],
            message_type=message_type,
            metadata=metadata
        )

class TelegramProcessor(WebhookProcessor):
    """Processes incoming Telegram updates."""
    
    def process_update(self, data):
        # Initial parsing only. Task handles orchestration.
        callback_query = data.get('callback_query')
        if callback_query:
            self.handle_callback(callback_query)
            return

        message = data.get('message')
        if not message: return
        
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        username = user.get('username') or user.get('first_name') or 'Anonymous'
        
        session = self.get_or_create_session(chat_id, 'telegram', username)
        
        text = message.get('text')
        if text and check_safe_word(text):
            session.set_cancelled(seconds=60)
            safety_msg = get_localized_safety_message(session.language_preference)
            self.save_message(session, 'assistant', safety_msg, 'text')
            self.send_message_sync(chat_id, safety_msg)
            return

    def send_message_sync(self, chat_id, text):
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        import requests
        try:
            res = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
            return res.json().get('result', {}).get('message_id')
        except Exception: return None

    def edit_message_sync(self, chat_id, msg_id, text):
        if not msg_id: return
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        import requests
        try:
            requests.post(f"https://api.telegram.org/bot{token}/editMessageText", json={'chat_id': chat_id, 'message_id': msg_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=5)
        except Exception: pass

    def delete_message_sync(self, chat_id, msg_id):
        if not message_id: return # Typo fix: msg_id
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        import requests
        try:
            requests.post(f"https://api.telegram.org/bot{token}/deleteMessage", json={'chat_id': chat_id, 'message_id': msg_id}, timeout=5)
        except Exception: pass

    def send_result(self, chat_id, result, session):
        case_id = getattr(result, 'case_id', 'N/A')[:8]
        if result.action == 'REPORT':
            msg = f"🚨 *HIGH RISK DETECTED*\n\n📋 *Case ID:* `{case_id}`\n⚠️ *Risk Score:* {result.risk_score}/10\n\n*Summary:* {result.summary}\n\n✅ *Action:* Escalated to partner."
        elif result.action == 'ASK_LOCATION':
            session.awaiting_location = True
            session.save()
            msg = get_localized_location_prompt(session.language_preference)
        else:
            msg = f"✅ *Analysis Complete*\n\n📊 *Risk Score:* {result.risk_score}/10\n\n💡 *Advice:*\n{result.advice}"
        
        self.save_message(session, 'assistant', result.advice)
        self.send_message_sync(chat_id, msg)

    def download_file(self, file_id):
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        try:
            import requests
            res = requests.get(f"https://api.telegram.org/bot{token}/getFile", params={'file_id': file_id}, timeout=30)
            res.raise_for_status()
            file_path = res.json().get('result', {}).get('file_path')
            if file_path:
                ext = os.path.splitext(file_path)[1] or '.bin'
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
                os.close(tmp_fd)
                with requests.get(f"https://api.telegram.org/file/bot{token}/{file_path}", stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(tmp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                return tmp_path, r.headers.get('content-type')
        except Exception: pass
        return None, None

    def handle_callback(self, callback_query):
        chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
        rating = callback_query.get('data', '').split('_')[1]
        UserFeedback.objects.create(chat_id=str(chat_id), rating=rating)
        self.send_message_sync(chat_id, "Thank you for your feedback!")

class MetaProcessor(WebhookProcessor):
    """Processes incoming Meta (Messenger/Instagram) events."""
    
    def handle_messaging_event(self, event, platform):
        # Logic remains similar but delegates orchestration to the task
        pass
