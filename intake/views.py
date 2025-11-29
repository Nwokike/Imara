import json
import logging
import os
import hashlib
import hmac
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings

from .services import report_processor
from .forms import ReportForm

logger = logging.getLogger(__name__)


class HomeView(View):
    def get(self, request):
        return render(request, 'intake/index.html')


def offline_view(request):
    return render(request, 'offline.html')


def serviceworker_view(request):
    sw_content = """
const CACHE_NAME = 'imara-pwa-v1';
const OFFLINE_URL = '/offline/';

const STATIC_ASSETS = [
    '/',
    '/offline/',
    '/static/css/styles.css',
    '/static/js/main.js',
    '/static/manifest.json',
    '/static/images/logo.png'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {
                if (response.status === 200) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request)
                    .then(cachedResponse => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        if (event.request.mode === 'navigate') {
                            return caches.match(OFFLINE_URL);
                        }
                        return new Response('', {
                            status: 408,
                            statusText: 'Offline'
                        });
                    });
            })
    );
});
"""
    return HttpResponse(sw_content, content_type='application/javascript')


class ReportFormView(View):
    def get(self, request):
        form = ReportForm()
        return render(request, 'intake/report_form.html', {'form': form})
    
    def post(self, request):
        form = ReportForm(request.POST, request.FILES)
        
        if form.is_valid():
            text = form.cleaned_data.get('message_text')
            image = form.cleaned_data.get('screenshot')
            audio = form.cleaned_data.get('voice_note')
            email = form.cleaned_data.get('email')
            
            if image:
                result = report_processor.process_image_report(
                    image_file=image,
                    source="web",
                    reporter_email=email,
                    additional_text=text
                )
            elif audio:
                result = report_processor.process_audio_report(
                    audio_file=audio,
                    source="web",
                    reporter_email=email
                )
            elif text:
                result = report_processor.process_text_report(
                    text=text,
                    source="web",
                    reporter_email=email
                )
            else:
                return render(request, 'intake/report_form.html', {
                    'form': form,
                    'error': 'Please provide at least a message, screenshot, or voice note.'
                })
            
            return render(request, 'intake/result.html', {'result': result})
        
        return render(request, 'intake/report_form.html', {'form': form})


class ResultView(View):
    def get(self, request):
        return redirect('report_form')


SAFE_WORDS = ['IMARA STOP', 'STOP', 'CANCEL', 'HELP ME', 'EXIT', 'EMERGENCY']

@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            logger.info(f"Received Telegram update: {data}")
            
            callback_query = data.get('callback_query')
            if callback_query:
                self.handle_callback(callback_query)
                return HttpResponse(status=200)
            
            self.process_update(data)
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return HttpResponse(status=200)
    
    def get_or_create_session(self, chat_id, username=None):
        from triage.models import ChatSession
        session, created = ChatSession.objects.get_or_create(
            chat_id=str(chat_id),
            defaults={'username': username, 'platform': 'telegram'}
        )
        if username and session.username != username:
            session.username = username
            session.save()
        return session
    
    def save_message(self, session, role, content, message_type='text', metadata=None):
        from triage.models import ChatMessage
        return ChatMessage.objects.create(
            session=session,
            role=role,
            content=content[:2000],
            message_type=message_type,
            metadata=metadata
        )
    
    def check_safe_word(self, text):
        if not text:
            return False
        text_upper = text.upper().strip()
        for safe_word in SAFE_WORDS:
            if safe_word in text_upper:
                return True
        return False
    
    def handle_callback(self, callback_query):
        import requests
        
        chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
        callback_data = callback_query.get('data', '')
        callback_id = callback_query.get('id')
        
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            return
        
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={'callback_query_id': callback_id},
                timeout=10
            )
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")
        
        if callback_data.startswith('feedback_'):
            from triage.models import UserFeedback
            parts = callback_data.split('_')
            rating = parts[1] if len(parts) > 1 else 'unknown'
            case_id = parts[2] if len(parts) > 2 else None
            
            UserFeedback.objects.create(
                chat_id=str(chat_id),
                case_id=case_id,
                rating=rating
            )
            
            if rating == 'helpful':
                self.send_message(chat_id, "Thank you for your feedback! We're glad we could help.")
            else:
                self.send_message(chat_id, "Thank you for your feedback. We'll work to improve our service.")
    
    def process_update(self, update):
        import requests
        
        message = update.get('message')
        if not message:
            return
        
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        username = user.get('username') or user.get('first_name') or 'Anonymous'
        
        session = self.get_or_create_session(chat_id, username)
        
        text = message.get('text')
        photo = message.get('photo')
        voice = message.get('voice')
        audio = message.get('audio')
        document = message.get('document')
        
        if text and self.check_safe_word(text):
            session.clear_pending_state()
            self.send_message(chat_id, "🛡️ I've stopped all current processes. You're safe here.\n\nIf you're in immediate danger, please contact local emergency services.\n\nType /start when you're ready to continue.")
            return
        
        if session.awaiting_location and text:
            self.handle_location_response(chat_id, text, session)
            return
        
        if text and text.startswith('/'):
            self.handle_command(chat_id, text, username)
            return
        
        if photo:
            self.save_message(session, 'user', '[Image]', 'image')
            self.handle_photo(chat_id, photo, username, message.get('caption'), session)
        elif voice or audio:
            voice_data = voice or audio
            self.save_message(session, 'user', '[Voice Note]', 'voice')
            self.handle_voice(chat_id, voice_data, username, session)
        elif text:
            self.save_message(session, 'user', text, 'text')
            self.handle_text(chat_id, text, username, session)
        elif document:
            mime_type = document.get('mime_type', '')
            if mime_type.startswith('image/'):
                self.save_message(session, 'user', '[Document Image]', 'image')
                self.handle_document_image(chat_id, document, username, message.get('caption'), session)
            elif mime_type.startswith('audio/'):
                self.save_message(session, 'user', '[Document Audio]', 'audio')
                self.handle_document_audio(chat_id, document, username, session)
            else:
                self.send_message(chat_id, "I can analyze text messages, screenshots, and voice notes. Please forward one of these to me.")
        else:
            self.send_message(chat_id, "Forward me any abusive message, screenshot, or voice note and I'll analyze it for you.")
    
    def handle_location_response(self, chat_id, text, session):
        session.last_detected_location = text
        pending_data = session.pending_report_data or {}
        session.awaiting_location = False
        session.pending_report_data = None
        session.save()
        
        original_text = pending_data.get('text', '')
        if original_text:
            from triage.decision_engine import DecisionEngine
            engine = DecisionEngine()
            
            context = session.get_conversation_context(limit=10)
            context.append(f"User location: {text}")
            
            result = report_processor.process_text_report(
                text=original_text,
                source="telegram",
                reporter_handle=f"@{session.username}",
                location_hint=text
            )
            
            self.send_result(chat_id, result, session)
    
    def handle_command(self, chat_id, text, username):
        command = text.split()[0].lower()
        
        if command == '/start':
            welcome_msg = """🛡️ Welcome to Project Imara - Your Digital Bodyguard

I'm here to help protect you from online harassment and threats.

*How to use me:*
📱 Forward any abusive message to me
📸 Send a screenshot of threats
🎤 Send a voice note of harassment

I'll analyze the content and:
• Give you advice for minor issues
• Alert authorities for serious threats

Your safety is my priority. Everything you share is confidential.

Ready when you are. 💪"""
            self.send_message(chat_id, welcome_msg)
            
        elif command == '/help':
            help_msg = """🆘 *How I Can Help*

*Forward Messages:* Forward any abusive message directly to me.

*Screenshots:* Send photos of threatening conversations.

*Voice Notes:* Send audio recordings of harassment.

*What I Do:*
1️⃣ Analyze the threat level
2️⃣ Provide advice for minor issues
3️⃣ Report serious threats to authorities

*Commands:*
/start - Welcome message
/help - This help message
/status - Check if I'm working

Stay safe! 🛡️"""
            self.send_message(chat_id, help_msg)
            
        elif command == '/status':
            self.send_message(chat_id, "✅ I'm online and ready to help protect you!")
            
        else:
            self.send_message(chat_id, "I don't recognize that command. Type /help to see what I can do.")
    
    def handle_text(self, chat_id, text, username, session=None):
        self.send_message(chat_id, "🔍 Analyzing your message...")
        
        context = session.get_conversation_context(limit=10) if session else None
        
        from triage.decision_engine import DecisionEngine
        engine = DecisionEngine()
        triage_result = engine.analyze_text(text, context)
        
        if triage_result.needs_location:
            if session:
                session.awaiting_location = True
                session.pending_report_data = {'text': text, 'type': 'text'}
                session.save()
            
            self.send_message(chat_id, "⚠️ This appears to be a serious threat that may need to be reported to authorities.\n\n📍 To help us connect you with the right authorities, please tell me:\n*Which city and country are you in?*\n\n(Example: Lagos, Nigeria or Nairobi, Kenya)")
            return
        
        location_hint = session.last_detected_location if session else None
        
        result = report_processor.process_text_report(
            text=text,
            source="telegram",
            reporter_handle=f"@{username}",
            location_hint=location_hint
        )
        
        self.send_result(chat_id, result, session)
    
    def handle_photo(self, chat_id, photos, username, caption=None, session=None):
        self.send_message(chat_id, "🔍 Analyzing your screenshot...")
        
        largest_photo = max(photos, key=lambda p: p.get('file_size', 0))
        file_id = largest_photo.get('file_id')
        
        image_bytes, mime_type = self.download_file(file_id)
        
        if image_bytes:
            from io import BytesIO
            
            file_obj = BytesIO(image_bytes)
            file_obj.seek(0)
            
            location_hint = session.last_detected_location if session else None
            
            result = report_processor.process_image_report(
                image_file=file_obj,
                source="telegram",
                reporter_handle=f"@{username}",
                additional_text=caption,
                location_hint=location_hint
            )
            
            self.send_result(chat_id, result, session)
        else:
            self.send_message(chat_id, "❌ Sorry, I couldn't download the image. Please try again.")
    
    def handle_voice(self, chat_id, voice_data, username, session=None):
        self.send_message(chat_id, "🔍 Analyzing your voice note...")
        
        file_id = voice_data.get('file_id')
        audio_bytes, mime_type = self.download_file(file_id)
        
        if audio_bytes:
            import tempfile
            
            ext = '.ogg' if 'ogg' in (mime_type or '') else '.mp3'
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            from django.core.files.uploadedfile import SimpleUploadedFile
            audio_file = SimpleUploadedFile(
                name=f"voice{ext}",
                content=audio_bytes,
                content_type=mime_type or 'audio/ogg'
            )
            
            location_hint = session.last_detected_location if session else None
            
            result = report_processor.process_audio_report(
                audio_file=audio_file,
                source="telegram",
                reporter_handle=f"@{username}",
                location_hint=location_hint
            )
            
            os.unlink(tmp_path)
            
            self.send_result(chat_id, result, session)
        else:
            self.send_message(chat_id, "❌ Sorry, I couldn't download the voice note. Please try again.")
    
    def handle_document_image(self, chat_id, document, username, caption=None, session=None):
        self.handle_photo(chat_id, [document], username, caption, session)
    
    def handle_document_audio(self, chat_id, document, username, session=None):
        self.handle_voice(chat_id, document, username, session)
    
    def download_file(self, file_id):
        import requests
        
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            return None, None
        
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={'file_id': file_id},
                timeout=30
            )
            response.raise_for_status()
            file_info = response.json().get('result', {})
            file_path = file_info.get('file_path')
            
            if file_path:
                file_response = requests.get(
                    f"https://api.telegram.org/file/bot{token}/{file_path}",
                    timeout=60
                )
                file_response.raise_for_status()
                
                mime_type = file_response.headers.get('content-type', 'application/octet-stream')
                return file_response.content, mime_type
                
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
        
        return None, None
    
    def send_result(self, chat_id, result, session=None):
        case_id = result.get('case_id', 'N/A')[:8]
        
        if session:
            response_content = f"Case {case_id}: {result.get('summary', 'Analysis complete')}"
            self.save_message(session, 'assistant', response_content, 'text')
        
        if result.get('action') == 'report':
            authority_name = result.get('authority_name', 'Local Authority')
            authority_email = result.get('authority_email', '')
            
            authority_info = ""
            if authority_name:
                authority_info = f"\n\n📧 *Sent To:*\n{authority_name}"
                if authority_email:
                    authority_info += f"\n_{authority_email}_"
            
            msg = f"""🚨 *HIGH RISK DETECTED*

📋 *Case ID:* `{case_id}`
⚠️ *Risk Score:* {result.get('risk_score', 'N/A')}/10

*Summary:* {result.get('summary', 'Threat detected')}

✅ *Action Taken:* Your report has been forwarded to the appropriate authorities.{authority_info}

⚡ *Safety Reminder:* Consider deleting this conversation if someone might check your phone. Type STOP anytime if you feel unsafe.

Keep this Case ID for your records. Stay safe. 🛡️"""
            
            self.send_message_with_feedback(chat_id, msg, case_id)
        else:
            msg = f"""✅ *Analysis Complete*

📋 *Case ID:* `{case_id}`
📊 *Risk Score:* {result.get('risk_score', 'N/A')}/10

*Summary:* {result.get('summary', 'Content analyzed')}

💡 *Advice:*
{result.get('advice', 'Stay safe and document any further incidents.')}

You're not alone. We're here to help. 🛡️"""
            
            self.send_message_with_feedback(chat_id, msg, case_id)
    
    def send_message_with_feedback(self, chat_id, text, case_id):
        import requests
        
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            return
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👍 Helpful", "callback_data": f"feedback_helpful_{case_id}"},
                    {"text": "👎 Not Helpful", "callback_data": f"feedback_not_helpful_{case_id}"}
                ]
            ]
        }
        
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'Markdown',
                    'reply_markup': keyboard
                },
                timeout=10
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message with feedback: {e}")
            self.send_message(chat_id, text)
    
    def send_message(self, chat_id, text):
        import requests
        
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            return
        
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'Markdown'
                },
                timeout=10
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")


def health_check(request):
    return JsonResponse({'status': 'healthy', 'service': 'Project Imara'})


def keep_alive(request):
    return HttpResponse("OK", content_type="text/plain")
