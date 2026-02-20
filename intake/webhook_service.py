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
from triage.decision_engine import decision_engine
from .services import report_processor
from .meta_service import meta_messenger
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
        # 1. Handle Callbacks (Feedback)
        callback_query = data.get('callback_query')
        if callback_query:
            self.handle_callback(callback_query)
            return

        message = data.get('message')
        if not message:
            return
        
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        username = user.get('username') or user.get('first_name') or 'Anonymous'
        
        session = self.get_or_create_session(chat_id, 'telegram', username)
        
        if session.is_cancelled():
            return

        text = message.get('text')
        photo = message.get('photo')
        voice = message.get('voice')
        audio = message.get('audio')
        
        # 2. Safe word check
        if text and check_safe_word(text):
            session.set_cancelled(seconds=60)
            safety_msg = get_localized_safety_message(session.language_preference)
            self.save_message(session, 'assistant', safety_msg, 'text')
            self.send_message_sync(chat_id, safety_msg)
            return
        
        # 3. Commands
        if text and text.startswith('/'):
            self.handle_command(chat_id, text, username)
            return
        
        # 4. Location Response
        if session.awaiting_location and text:
            self.handle_location_response(chat_id, text, session)
            return

        # 5. Media/Text Orchestration
        if text:
            self.save_message(session, 'user', text, 'text')
            self.handle_text(chat_id, text, username, session)
        elif photo:
            self.save_message(session, 'user', '[Image]', 'image')
            self.handle_photo(chat_id, photo, username, message.get('caption'), session)
        elif voice or audio:
            self.save_message(session, 'user', '[Voice Note]', 'voice')
            self.handle_voice(chat_id, voice or audio, username, session)

    def handle_text(self, chat_id, text, username, session):
        # Initial status message
        msg_id = self.send_message_sync(chat_id, "💭 Aunty Imara is listening...")
        
        def on_step(agent, detail):
            self.edit_message_sync(chat_id, msg_id, f"💭 {agent} Agent: {detail}")

        result = decision_engine.chat_orchestration(
            text, 
            history=session.get_messages_for_llm(limit=10),
            metadata={"last_interaction_age": session.get_last_interaction_age()},
            on_step=on_step
        )
        
        self.delete_message_sync(chat_id, msg_id)
        self.send_result(chat_id, result, session)

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
        if not msg_id: return
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        import requests
        try:
            requests.post(f"https://api.telegram.org/bot{token}/deleteMessage", json={'chat_id': chat_id, 'message_id': msg_id}, timeout=5)
        except Exception: pass

    def handle_command(self, chat_id, text, username):
        command = text.split()[0].lower()
        if command == '/start':
            msg = "🛡️ Welcome to Project Imara - Your Digital Bodyguard\n\nI'm here to help protect you from online threats."
        elif command == '/help':
            msg = "🆘 *How I Can Help*\n\nForward abusive messages, screenshots, or voice notes. I'll assess the threat level."
        elif command == '/status':
            msg = "✅ I'm online and ready!"
        else:
            msg = "I don't recognize that command. Type /help."
        self.send_message_sync(chat_id, msg)

    def handle_location_response(self, chat_id, text, session):
        self.save_message(session, 'user', text, 'text')
        session.last_detected_location = text
        session.awaiting_location = False
        session.save()
        self.send_message_sync(chat_id, f"📍 Got it - {text}. Updating your report...")

    def handle_photo(self, chat_id, photos, username, caption, session):
        msg_id = self.send_message_sync(chat_id, "🔍 Analyzing your screenshot...")
        def on_step(agent, detail):
            self.edit_message_sync(chat_id, msg_id, f"🔍 {agent} Agent: {detail}")

        largest = max(photos, key=lambda p: p.get('file_size', 0))
        file_id = largest.get('file_id')
        image_path, _ = self.download_file(file_id)
        if image_path:
            try:
                result = decision_engine.chat_orchestration(
                    text=caption or "Visual Evidence",
                    history=session.get_messages_for_llm(limit=10),
                    image_url=image_path,
                    metadata={"source": "telegram", "chat_id": chat_id},
                    on_step=on_step
                )
                self.delete_message_sync(chat_id, msg_id)
                self.send_result(chat_id, result, session)
            finally:
                if os.path.exists(image_path): os.unlink(image_path)

    def handle_voice(self, chat_id, voice_data, username, session):
        msg_id = self.send_message_sync(chat_id, "🎤 Transcribing voice note...")
        def on_step(agent, detail):
            self.edit_message_sync(chat_id, msg_id, f"🎤 {agent} Agent: {detail}")

        file_id = voice_data.get('file_id')
        audio_path, _ = self.download_file(file_id)
        if audio_path:
            try:
                from triage.clients.groq_client import get_groq_client
                text = get_groq_client().transcribe_audio(audio_path)
                result = decision_engine.chat_orchestration(
                    text=f"[Voice Note]: {text}",
                    history=session.get_messages_for_llm(limit=10),
                    metadata={"source": "telegram", "chat_id": chat_id},
                    on_step=on_step
                )
                self.delete_message_sync(chat_id, msg_id)
                self.send_result(chat_id, result, session)
            finally:
                if os.path.exists(audio_path): os.unlink(audio_path)

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

    def send_result(self, chat_id, result, session):
        case_id = "N/A"
        if result.action == 'REPORT':
            msg = f"🚨 *HIGH RISK DETECTED*\n\n📋 *Case ID:* `{case_id}`\n⚠️ *Risk Score:* {result.risk_score}/10\n\n*Summary:* {result.summary}\n\n✅ *Action:* Escalated to partner."
        elif result.action == 'ASK_LOCATION':
            session.awaiting_location = True
            session.save()
            msg = get_localized_location_prompt(session.language_preference)
        else:
            msg = f"✅ *Analysis Complete*\n\n📊 *Risk Score:* {result.risk_score}/10\n\n💡 *Advice:*\n{result.advice}"
        
        self.save_message(session, 'assistant', result.advice)
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        import requests
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'}, timeout=10)
        except Exception: pass

    def handle_callback(self, callback_query):
        chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
        rating = callback_query.get('data', '').split('_')[1]
        UserFeedback.objects.create(chat_id=str(chat_id), rating=rating)
        self.send_message_sync(chat_id, "Thank you for your feedback!")

class MetaProcessor(WebhookProcessor):
    """Processes incoming Meta (Messenger/Instagram) events."""
    
    def handle_messaging_event(self, event, platform):
        sender_id = event.get('sender', {}).get('id')
        if not sender_id: return
        session = self.get_or_create_session(sender_id, platform)
        if session.is_cancelled(): return

        message = event.get('message', {})
        text = message.get('text')
        if text:
            if check_safe_word(text):
                session.set_cancelled(seconds=60)
                meta_messenger.send_text_message(sender_id, get_localized_safety_message(session.language_preference), platform)
                return
            
            self.save_message(session, 'user', text)
            meta_messenger.send_typing_indicator(sender_id)
            result = decision_engine.chat_orchestration(
                text, 
                history=session.get_messages_for_llm(limit=10),
                metadata={"last_interaction_age": session.get_last_interaction_age()}
            )
            self._send_meta_result(sender_id, result, session, platform)

    def _send_meta_result(self, sender_id, result, session, platform):
        if result.action == 'ASK_LOCATION':
            session.awaiting_location = True
            session.save()
            msg = get_localized_location_prompt(session.language_preference)
        else:
            msg = f"Analysis: {result.summary}\nRisk: {result.risk_score}/10\nAdvice: {result.advice}"
        meta_messenger.send_text_message(sender_id, msg, platform)
