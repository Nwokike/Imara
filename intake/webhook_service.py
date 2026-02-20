"""
Webhook processing services for Telegram and Meta platforms.
Extracted from views to support persistent background tasks.
"""
import logging
import json
import os
import tempfile
import requests
from django.conf import settings
from django.core.files import File
from django.db import close_old_connections

from triage.models import ChatSession, ChatMessage, UserFeedback
from triage.conversation_engine import conversation_engine
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
        
        text = message.get('text')
        photo = message.get('photo')
        voice = message.get('voice')
        audio = message.get('audio')
        document = message.get('document')
        
        # Safe word check
        if text and check_safe_word(text):
            session.set_cancelled(seconds=60)
            safety_msg = get_localized_safety_message(session.language_preference)
            self.save_message(session, 'assistant', safety_msg, 'text')
            self.send_message(chat_id, safety_msg)
            return
        
        # Commands
        if text and text.startswith('/'):
            self.handle_command(chat_id, text, username)
            return
        
        if text:
            if session.awaiting_location:
                self.handle_location_response(chat_id, text, session)
            else:
                self.save_message(session, 'user', text, 'text')
                self.handle_text(chat_id, text, username, session)
        elif photo:
            self.save_message(session, 'user', '[Image]', 'image')
            self.handle_photo(chat_id, photo, username, message.get('caption'), session)
        elif voice or audio:
            self.save_message(session, 'user', '[Voice Note]', 'voice')
            self.handle_voice(chat_id, voice or audio, username, session)
        elif document:
            mime_type = document.get('mime_type', '')
            if mime_type.startswith('image/'):
                self.save_message(session, 'user', '[Document Image]', 'image')
                self.handle_document_image(chat_id, document, username, message.get('caption'), session)
            elif mime_type.startswith('audio/'):
                self.save_message(session, 'user', '[Document Audio]', 'audio')
                self.handle_document_audio(chat_id, document, username, session)
            else:
                self.send_message(chat_id, "I can analyze text, screenshots, and voice notes. Please forward one of these.")
        else:
            self.send_message(chat_id, "Forward me any abusive message, screenshot, or voice note and I'll analyze it for you.")

    def handle_text(self, chat_id, text, username, session):
        # Show typing indicator acknowledgment
        self.send_message(chat_id, "💭 ...")
        
        response = conversation_engine.process_message(session, text, 'text')
        
        session.conversation_state = response.state.value
        if response.gathered_info:
            session.gathered_evidence = {**session.gathered_evidence, **response.gathered_info}
        if response.detected_language:
            session.language_preference = response.detected_language
        session.save()
        
        self.save_message(session, 'assistant', response.message, 'text')
        
        # Check if cancelled during processing
        session.refresh_from_db()
        if session.is_cancelled():
            return
        
        self.send_message(chat_id, response.message)
        
        if response.should_create_report:
            self._create_and_send_report(chat_id, session, username, response.gathered_info)
        elif response.is_low_risk:
            session.conversation_state = 'IDLE'
            session.gathered_evidence = {}
            session.save()

    def handle_callback(self, callback_query):
        chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
        callback_data = callback_query.get('data', '')
        callback_id = callback_query.get('id')
        
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token: return
        
        try:
            requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={'callback_query_id': callback_id}, timeout=10)
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")
        
        if callback_data.startswith('feedback_'):
            parts = callback_data.split('_')
            rating = parts[1] if len(parts) > 1 else 'unknown'
            case_id = parts[2] if len(parts) > 2 else None
            
            UserFeedback.objects.create(chat_id=str(chat_id), case_id=case_id, rating=rating)
            
            msg = "Thank you for your feedback! We're glad we could help." if rating == 'helpful' else "Thank you for your feedback. We'll work to improve our service."
            self.send_message(chat_id, msg)

    def handle_command(self, chat_id, text, username):
        command = text.split()[0].lower()
        if command == '/start':
            msg = "🛡️ Welcome to Project Imara - Your Digital Bodyguard\n\nI'm here to help protect you from online harassment and threats.\n\n*How to use me:*\n📱 Forward any abusive message\n📸 Send a screenshot\n🎤 Send a voice note\n\nYour safety is my priority."
        elif command == '/help':
            msg = "🆘 *How I Can Help*\n\nForward abusive messages, screenshots, or voice notes. I'll analyze the threat level and provide advice or alert verified partners for serious threats."
        elif command == '/status':
            msg = "✅ I'm online and ready to help protect you!"
        else:
            msg = "I don't recognize that command. Type /help to see what I can do."
        self.send_message(chat_id, msg)

    def handle_location_response(self, chat_id, text, session):
        self.save_message(session, 'user', text, 'text')
        session.last_detected_location = text
        pending_data = session.pending_report_data or {}
        session.awaiting_location = False
        session.pending_report_data = None
        session.conversation_state = 'IDLE'
        session.save()
        
        case_id = pending_data.get('case_id')
        original_text = pending_data.get('text', '')
        
        if case_id:
            self.send_message(chat_id, f"📍 Got it - {text}. Updating your case...")
            result = report_processor.update_location_and_dispatch(case_id, text)
            if result.get('success'):
                msg = f"✅ *Report Escalate*\n\nYour case (`{case_id[:8]}`) has been updated and sent to {result.get('partner_name')}.\n\nStay safe. 🛡️"
            else:
                msg = "⚠️ We updated your location but couldn't dispatch to a partner yet. We'll review it manually."
            self.send_message(chat_id, msg)
        elif original_text:
            self.send_message(chat_id, f"📍 Got it - {text}. Processing your report now...")
            result = report_processor.process_text_report(text=original_text, source="telegram", reporter_handle=f"@{session.username}", location_hint=text)
            self.send_result(chat_id, result, session)
        else:
            self.send_message(chat_id, f"📍 Location saved as {text}. You can now send me content to analyze.")

    def handle_photo(self, chat_id, photos, username, caption=None, session=None):
        self.send_message(chat_id, "🔍 Analyzing your screenshot...")
        largest_photo = max(photos, key=lambda p: p.get('file_size', 0))
        file_id = largest_photo.get('file_id')
        image_path, _ = self.download_file(file_id)
        if image_path:
            try:
                with open(image_path, 'rb') as f:
                    django_file = File(f, name=os.path.basename(image_path))
                    result = report_processor.process_image_report(image_file=django_file, source="telegram", reporter_handle=f"@{username}", additional_text=caption, location_hint=session.last_detected_location if session else None)
                self.send_result(chat_id, result, session)
            finally:
                if os.path.exists(image_path): os.unlink(image_path)
        else:
            self.send_message(chat_id, "❌ Sorry, I couldn't download the image.")

    def handle_voice(self, chat_id, voice_data, username, session=None):
        self.send_message(chat_id, "🔍 Analyzing your voice note...")
        file_id = voice_data.get('file_id')
        audio_path, _ = self.download_file(file_id)
        if audio_path:
            try:
                with open(audio_path, 'rb') as f:
                    django_file = File(f, name=os.path.basename(audio_path))
                    result = report_processor.process_audio_report(audio_file=django_file, source="telegram", reporter_handle=f"@{username}", location_hint=session.last_detected_location if session else None)
                self.send_result(chat_id, result, session)
            finally:
                if os.path.exists(audio_path): os.unlink(audio_path)
        else:
            self.send_message(chat_id, "❌ Sorry, I couldn't download the voice note.")

    def handle_document_image(self, chat_id, document, username, caption=None, session=None):
        self.handle_photo(chat_id, [document], username, caption, session)

    def handle_document_audio(self, chat_id, document, username, session=None):
        self.handle_voice(chat_id, document, username, session)

    def download_file(self, file_id):
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        try:
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
        except Exception as e:
            logger.error(f"Telegram download failed: {e}")
        return None, None

    def _create_and_send_report(self, chat_id, session, username, gathered_info):
        location = gathered_info.get('location') or session.last_detected_location or 'Unknown'
        risk_score = gathered_info.get('risk_score', 7)
        reporter_name = (gathered_info.get('reporter_name') or '').strip()
        contact_preference = (gathered_info.get('contact_preference') or '').strip()
        incident_description = (gathered_info.get('incident_description') or gathered_info.get('evidence_summary') or '').strip()
        
        missing = []
        if not reporter_name: missing.append("your name (or a safe nickname)")
        if risk_score >= 7 and (not location or location == "Unknown"): missing.append("your city and country")
        if not incident_description: missing.append("a description of what happened")
        if not contact_preference: missing.append("contact preference (email/phone/none)")
        
        if missing:
            session.conversation_state = 'GATHERING'
            session.save()
            prompt = "I need a bit more info to escalate this:\n\n- " + "\n- ".join(missing)
            self.send_message(chat_id, prompt)
            return

        report_text = self._build_report_text(session, gathered_info)
        result = report_processor.process_text_report(text=report_text, source="telegram", reporter_handle=f"@{username}", location_hint=location, reporter_name=reporter_name, reporter_email=gathered_info.get('reporter_email'), contact_preference=contact_preference, perpetrator_info=gathered_info.get('perpetrator_info'))
        session.reset_conversation()
        self.send_result(chat_id, result, session)

    def _build_report_text(self, session, gathered_info):
        parts = [f"{k.replace('_', ' ').title()}: {v}" for k, v in gathered_info.items() if v and k != 'user_confirmed']
        user_messages = session.messages.filter(role='user').order_by('-created_at')[:5]
        for msg in reversed(list(user_messages)):
            if '[Image]' not in msg.content and '[Voice Note]' not in msg.content:
                parts.append(f"User: {msg.content}")
        return "\n".join(parts)

    def send_result(self, chat_id, result, session=None):
        if session:
            session.refresh_from_db()
            if session.is_cancelled(): return
        
        case_id = result.get('case_id', 'N/A')[:8]
        if result.get('action') == 'report':
            msg = f"🚨 *HIGH RISK DETECTED*\n\n📋 *Case ID:* `{case_id}`\n⚠️ *Risk Score:* {result.get('risk_score')}/10\n\n*Summary:* {result.get('summary')}\n\n✅ *Action:* Escalated to support partner.\n\n⚡ *Safety:* Delete this chat if needed."
            self.send_message_with_feedback(chat_id, msg, case_id)
        elif result.get('action') == 'ask_location':
            if session:
                session.pending_report_data = {'case_id': result.get('case_id'), 'summary': result.get('summary'), 'original_action': 'report'}
                session.awaiting_location = True
                session.conversation_state = 'ASKING_LOCATION'
                session.save()
            msg = get_localized_location_prompt(session.language_preference if session else 'english')
            self.send_message(chat_id, msg)
        else:
            msg = f"✅ *Analysis Complete*\n\n📋 *Case ID:* `{case_id}`\n📊 *Risk Score:* {result.get('risk_score')}/10\n\n💡 *Advice:*\n{result.get('advice')}"
            self.send_message_with_feedback(chat_id, msg, case_id)

    def send_message_with_feedback(self, chat_id, text, case_id):
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token: return
        keyboard = {"inline_keyboard": [[{"text": "👍 Helpful", "callback_data": f"feedback_helpful_{case_id}"}, {"text": "👎 Not Helpful", "callback_data": f"feedback_not_helpful_{case_id}"}]]}
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown', 'reply_markup': keyboard}, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send feedback: {e}")

    def send_message(self, chat_id, text):
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token: return
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send msg: {e}")

class MetaProcessor(WebhookProcessor):
    """Processes incoming Meta (Messenger/Instagram) events."""
    
    def handle_messaging_event(self, event, platform):
        sender_id = event.get('sender', {}).get('id')
        if not sender_id: return
        
        session = self.get_or_create_session(sender_id, platform)
        
        if 'message' in event:
            message = event['message']
            if message.get('quick_reply'):
                self._handle_quick_reply(sender_id, message['quick_reply'], session)
            elif 'text' in message:
                self._handle_text_message(sender_id, message['text'], session, platform)
            elif message.get('attachments'):
                for attachment in message['attachments']:
                    if attachment.get('type') == 'image': self._handle_image(sender_id, attachment, session, platform)
                    elif attachment.get('type') == 'audio': self._handle_audio(sender_id, attachment, session, platform)
        elif 'postback' in event:
            logger.info(f"Meta postback from {sender_id}: {event['postback'].get('payload')}")

    def _handle_text_message(self, sender_id, text, session, platform):
        if check_safe_word(text):
            session.set_cancelled(seconds=60)
            safety_msg = get_localized_safety_message(session.language_preference)
            self.save_message(session, 'assistant', safety_msg)
            meta_messenger.send_text_message(sender_id, safety_msg, platform)
            return
        
        if session.awaiting_location:
            session.last_detected_location = text
            session.awaiting_location = False
            session.save()
        
        self.save_message(session, 'user', text)
        meta_messenger.send_typing_indicator(sender_id)
        
        response = conversation_engine.process_message(session, text, 'text')
        session.conversation_state = response.state.value
        if response.gathered_info: session.gathered_evidence = {**session.gathered_evidence, **response.gathered_info}
        if response.detected_language: session.language_preference = response.detected_language
        session.save()
        
        self.save_message(session, 'assistant', response.message)
        session.refresh_from_db()
        if session.is_cancelled(): return
        
        meta_messenger.send_text_message(sender_id, response.message, platform)
        
        if response.should_create_report:
            self._create_and_send_report(sender_id, session, platform, response.gathered_info)
        elif response.is_low_risk:
            session.conversation_state = 'IDLE'
            session.gathered_evidence = {}
            session.save()

    def _handle_image(self, sender_id, attachment, session, platform):
        self.save_message(session, 'user', '[Image]', 'image')
        meta_messenger.send_text_message(sender_id, "🔍 Analyzing your screenshot...", platform)
        url = attachment.get('payload', {}).get('url')
        if not url: return
        try:
            res = requests.get(url, timeout=60, stream=True)
            res.raise_for_status()
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(tmp_fd)
            with open(tmp_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192): f.write(chunk)
            try:
                with open(tmp_path, 'rb') as f:
                    django_file = File(f, name='meta_image.jpg')
                    result = report_processor.process_image_report(image_file=django_file, source=platform, reporter_handle=f"meta:{sender_id}", location_hint=session.last_detected_location)
                self._send_result(sender_id, result, session, platform)
            finally:
                if os.path.exists(tmp_path): os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"Meta image error: {e}")

    def _handle_audio(self, sender_id, attachment, session, platform):
        self.save_message(session, 'user', '[Voice Note]', 'voice')
        meta_messenger.send_text_message(sender_id, "🔍 Analyzing your voice note...", platform)
        url = attachment.get('payload', {}).get('url')
        if not url: return
        try:
            res = requests.get(url, timeout=60, stream=True)
            res.raise_for_status()
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mp4')
            os.close(tmp_fd)
            with open(tmp_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192): f.write(chunk)
            try:
                with open(tmp_path, 'rb') as f:
                    django_file = File(f, name='meta_audio.mp4')
                    result = report_processor.process_audio_report(audio_file=django_file, source=platform, reporter_handle=f"meta:{sender_id}", location_hint=session.last_detected_location)
                self._send_result(sender_id, result, session, platform)
            finally:
                if os.path.exists(tmp_path): os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"Meta audio error: {e}")

    def _handle_quick_reply(self, sender_id, quick_reply, session):
        payload = quick_reply.get('payload', '')
        if payload.startswith('feedback_'):
            parts = payload.split('_')
            rating = parts[1] if len(parts) > 1 else 'unknown'
            UserFeedback.objects.create(chat_id=sender_id, case_id=parts[2] if len(parts) > 2 else None, rating=rating)
            meta_messenger.send_text_message(sender_id, "Thank you for your feedback!", session.platform)

    def _create_and_send_report(self, sender_id, session, platform, gathered_info):
        location = gathered_info.get('location') or session.last_detected_location or 'Unknown'
        risk_score = gathered_info.get('risk_score', 7)
        reporter_name = (gathered_info.get('reporter_name') or '').strip()
        contact_preference = (gathered_info.get('contact_preference') or '').strip()
        incident_description = (gathered_info.get('incident_description') or gathered_info.get('evidence_summary') or '').strip()
        
        missing = []
        if not reporter_name: missing.append("your name (or safe nickname)")
        if risk_score >= 7 and (not location or location == "Unknown"): missing.append("your city and country")
        if not incident_description: missing.append("a description of what happened")
        if not contact_preference: missing.append("how you want to be contacted")
        
        if missing:
            session.conversation_state = 'GATHERING'
            session.save()
            meta_messenger.send_text_message(sender_id, "To escalate safely, I need more info: " + ", ".join(missing), platform)
            return

        report_text = f"Incident: {incident_description}\nReporter: {reporter_name}\nLocation: {location}\nType: {gathered_info.get('threat_type')}"
        result = report_processor.process_text_report(text=report_text, source=platform, reporter_handle=f"meta:{sender_id}", location_hint=location, reporter_name=reporter_name, contact_preference=contact_preference)
        session.reset_conversation()
        self._send_result(sender_id, result, session, platform)

    def _send_result(self, sender_id, result, session, platform):
        session.refresh_from_db()
        if session.is_cancelled(): return
        case_id = result.get('case_id', 'N/A')[:8]
        if result.get('action') == 'report':
            msg = f"🚨 HIGH RISK DETECTED\n\n📋 Case ID: {case_id}\n⚠️ Risk Score: {result.get('risk_score')}/10\n\n✅ Action: Forwarded to support partner.\n\n⚡ Safety: Delete this chat if needed."
        elif result.get('action') == 'ask_location':
            if session:
                session.pending_report_data = {'case_id': result.get('case_id'), 'summary': result.get('summary'), 'original_action': 'report'}
                session.awaiting_location = True
                session.conversation_state = 'ASKING_LOCATION'
                session.save()
            msg = get_localized_location_prompt(session.language_preference if session else 'english')
        else:
            msg = f"✅ Analysis Complete\n\n📋 Case ID: {case_id}\n📊 Risk Score: {result.get('risk_score')}/10\n\n💡 Advice: {result.get('advice')}"
        
        buttons = [{"title": "👍 Helpful", "payload": f"feedback_helpful_{case_id}"}, {"title": "👎 Not Helpful", "payload": f"feedback_not_helpful_{case_id}"}]
        meta_messenger.send_message_with_buttons(sender_id, msg, buttons, platform)
