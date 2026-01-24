import json
import logging
import os
import tempfile
import requests
from concurrent.futures import ThreadPoolExecutor

from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.core.files import File
from django.db import close_old_connections
from django.utils.html import escape

from triage.models import ChatSession, ChatMessage, UserFeedback
from triage.decision_engine import DecisionEngine

from .services import report_processor
from .forms import ReportForm, ContactForm
from dispatch.tasks import send_email_task
from utils.ratelimit import form_ratelimit, telegram_webhook_ratelimit

logger = logging.getLogger(__name__)


from partners.models import PartnerOrganization

class HomeView(View):
    def get(self, request):
        # Fetch active, verified partner organizations for the support section
        partners = PartnerOrganization.objects.filter(
            is_active=True,
            is_verified=True
        ).order_by('jurisdiction', 'name')
        
        # Group by jurisdiction
        support_resources = {}
        for partner in partners:
            country = partner.jurisdiction
            if country not in support_resources:
                support_resources[country] = []
            support_resources[country].append({
                'name': partner.name,
                'phone': partner.phone,
                'email': partner.contact_email,
                'website': partner.website,
                'org_type': partner.get_org_type_display(),
            })
            
        return render(request, 'intake/index.html', {'support_resources': support_resources})


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
    
    @method_decorator(form_ratelimit)
    def post(self, request):
        # Security: Validate Cloudflare Turnstile
        from utils.captcha import validate_turnstile
        token = request.POST.get('cf-turnstile-response')
        is_valid, error_msg = validate_turnstile(token, request.META.get('REMOTE_ADDR'))
        
        if not is_valid:
            # Configure message for UI failure
            form = ReportForm(request.POST, request.FILES)
            return render(request, 'intake/report_form.html', {
                'form': form, 
                'error': error_msg
            })

        form = ReportForm(request.POST, request.FILES)
        
        if form.is_valid():
            text = form.cleaned_data.get('message_text')
            image = form.cleaned_data.get('screenshot')
            audio = form.cleaned_data.get('voice_note')
            name = (form.cleaned_data.get('name') or '').strip() or None
            email = form.cleaned_data.get('email')
            
            if image:
                result = report_processor.process_image_report(
                    image_file=image,
                    source="web",
                    reporter_email=email,
                    reporter_name=name or None,
                    additional_text=text
                )
            elif audio:
                result = report_processor.process_audio_report(
                    audio_file=audio,
                    source="web",
                    reporter_email=email,
                    reporter_name=name or None
                )
            elif text:
                result = report_processor.process_text_report(
                    text=text,
                    source="web",
                    reporter_email=email,
                    reporter_name=name or None
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
@method_decorator(telegram_webhook_ratelimit, name='post')
class TelegramWebhookView(View):
    # Reduced to 2 workers for 1GB RAM constraint
    _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="telegram_worker")

    def post(self, request):
        try:
            secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            expected_token = os.environ.get('TELEGRAM_SECRET_TOKEN')
            
            if expected_token and secret_token != expected_token:
                logger.warning(f"Invalid Telegram secret token: {secret_token}")
                return HttpResponse(status=403)

            data = json.loads(request.body)
            logger.debug(f"Received Telegram update: {data}")
            
            callback_query = data.get('callback_query')
            if callback_query:
                self.handle_callback(callback_query)
                return HttpResponse(status=200)
            
            self._executor.submit(self.process_update_task, data)
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return HttpResponse(status=200)

    def process_update_task(self, data):
        try:
            close_old_connections()
            self.process_update(data)
        except Exception as e:
            logger.error(f"Async update processing failed: {e}")
        finally:
            close_old_connections()
    
    def get_or_create_session(self, chat_id, username=None):
        """Get or create a session for this platform + chat_id combination."""
        session, created = ChatSession.objects.get_or_create(
            chat_id=str(chat_id),
            platform='telegram',
            defaults={'username': username}
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
        
        # Safe word check
        if text and self.check_safe_word(text):
            session.set_cancelled(seconds=60)
            
            safety_msg = self.get_localized_safety_message(session)
            self.save_message(session, 'assistant', safety_msg, 'text')
            self.send_message(chat_id, safety_msg)
            return
        
        # Commands
        if text and text.startswith('/'):
            self.handle_command(chat_id, text, username)
            return
        
        # All text messages go through conversation engine (which handles state)
        if text:
            self.save_message(session, 'user', text, 'text')
            self.handle_text(chat_id, text, username, session)
        elif photo:
            self.save_message(session, 'user', '[Image]', 'image')
            self.handle_photo(chat_id, photo, username, message.get('caption'), session)
        elif voice or audio:
            voice_data = voice or audio
            self.save_message(session, 'user', '[Voice Note]', 'voice')
            self.handle_voice(chat_id, voice_data, username, session)
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
        self.save_message(session, 'user', text, 'text')
        
        session.last_detected_location = text
        pending_data = session.pending_report_data or {}
        session.awaiting_location = False
        session.pending_report_data = None
        session.save()
        
        original_text = pending_data.get('text', '')
        if original_text:
            confirmation_msg = f"📍 Got it - {text}. Processing your report now..."
            self.save_message(session, 'assistant', confirmation_msg, 'text')
            self.send_message(chat_id, confirmation_msg)
            
            result = report_processor.process_text_report(
                text=original_text,
                source="telegram",
                reporter_handle=f"@{session.username}",
                location_hint=text
            )
            
            self.send_result(chat_id, result, session)
        else:
            saved_msg = f"📍 Location saved as {text}. You can now send me content to analyze."
            self.save_message(session, 'assistant', saved_msg, 'text')
            self.send_message(chat_id, saved_msg)
    
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
• Alert verified support partners for serious threats

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
3️⃣ Report serious threats to verified support partners

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
        """
        Handle text messages using the conversational AI engine.
        
        This method now supports multi-turn conversations with:
        - State machine for conversation flow
        - Empathetic dialogue with follow-up questions
        - Location collection before high-risk reports
        - User confirmation before filing reports
        - Historical context from past messages
        """
        if not session:
            session = self.get_or_create_session(chat_id, username)
        
        # Import conversation engine
        from triage.conversation_engine import conversation_engine, ConversationState
        
        # Show typing indicator / acknowledgment
        typing_msg = "💭 ..."
        self.send_message(chat_id, typing_msg)
        
        # Process through conversation engine
        response = conversation_engine.process_message(
            session=session,
            user_message=text,
            message_type='text'
        )
        
        # Update session state based on AI response
        session.conversation_state = response.state.value
        if response.gathered_info:
            session.gathered_evidence = {**session.gathered_evidence, **response.gathered_info}
        if response.detected_language:
            session.language_preference = response.detected_language

        # Track missing required fields for reliability
        try:
            from triage.decision_engine import decision_engine
            missing = decision_engine.check_required_fields(session, session.gathered_evidence)
            session.required_fields = missing
            session.gathered_required_info = {
                k: session.gathered_evidence.get(k)
                for k in ['reporter_name', 'location', 'incident_description', 'contact_preference', 'perpetrator_info']
                if session.gathered_evidence.get(k)
            }
            session.case_creation_pending = bool(response.should_create_report) and not missing
            session.last_ai_instruction = response.message[:2000]
        except Exception:
            # Never block user flow on bookkeeping
            pass
        session.save()
        
        # Save AI response to message history
        self.save_message(session, 'assistant', response.message, 'text')
        
        # Check if cancelled during processing
        session.refresh_from_db()
        if session.is_cancelled():
            return
        
        # Send the conversational response to user
        self.send_message(chat_id, response.message)
        
        # Handle report creation if AI says we're ready
        if response.should_create_report:
            self._create_and_send_report(chat_id, session, username, response.gathered_info)
        elif response.is_low_risk:
            # For low risk, we've already given advice - just log it
            logger.info(f"Low-risk advice given to {chat_id}")
            # Reset conversation state after advice
            session.conversation_state = 'IDLE'
            session.gathered_evidence = {}
            session.save()
    
    def _create_and_send_report(self, chat_id, session, username, gathered_info):
        """Create formal report after user confirmation and send result."""
        # Extract info from gathered evidence
        evidence_summary = gathered_info.get('evidence_summary', '')
        location = gathered_info.get('location') or session.last_detected_location or 'Unknown'
        threat_type = gathered_info.get('threat_type', 'threat')
        risk_score = gathered_info.get('risk_score', 7)
        reporter_name = (gathered_info.get('reporter_name') or '').strip()
        contact_preference = (gathered_info.get('contact_preference') or '').strip()
        incident_description = (gathered_info.get('incident_description') or evidence_summary or '').strip()
        
        missing = []
        if not reporter_name:
            missing.append("your name (or a safe nickname)")
        if (risk_score or 0) >= 7 and (not location or location == "Unknown"):
            missing.append("your city and country")
        if not incident_description:
            missing.append("a brief description of what happened")
        if not contact_preference:
            missing.append("how you want to be contacted (email/phone/none)")
        
        if missing:
            session.conversation_state = 'GATHERING'
            session.save()
            prompt = "To escalate this safely, I need a bit more information:\n\n- " + "\n- ".join(missing) + "\n\nYou can answer in one message."
            self.save_message(session, 'assistant', prompt, 'text')
            self.send_message(chat_id, prompt)
            return
        
        # Store location for future use
        if location and location != 'Unknown':
            session.last_detected_location = location
            session.save()
        
        # Build the report text from conversation history
        report_text = self._build_report_text(session, gathered_info)
        
        # Process the complete report
        result = report_processor.process_text_report(
            text=report_text,
            source="telegram",
            reporter_handle=f"@{username}",
            location_hint=location,
            reporter_name=reporter_name or None,
            contact_preference=contact_preference or None,
            perpetrator_info=gathered_info.get('perpetrator_info') or None,
        )
        
        # Reset conversation state
        session.conversation_state = 'IDLE'
        session.gathered_evidence = {}
        session.save()
        
        # Send result to user
        self.send_result(chat_id, result, session)
    
    def _build_report_text(self, session, gathered_info):
        """Build complete report text from conversation history and gathered info."""
        parts = []
        
        # Add gathered info summary
        if gathered_info.get('reporter_name'):
            parts.append(f"Reporter Name: {gathered_info['reporter_name']}")
        if gathered_info.get('contact_preference'):
            parts.append(f"Contact Preference: {gathered_info['contact_preference']}")
        if gathered_info.get('evidence_summary'):
            parts.append(f"Summary: {gathered_info['evidence_summary']}")
        if gathered_info.get('incident_description'):
            parts.append(f"Incident Description: {gathered_info['incident_description']}")
        if gathered_info.get('threat_type'):
            parts.append(f"Threat Type: {gathered_info['threat_type']}")
        if gathered_info.get('perpetrator_info'):
            parts.append(f"Perpetrator: {gathered_info['perpetrator_info']}")
        
        # Add user messages from conversation
        user_messages = session.messages.filter(role='user').order_by('-created_at')[:5]
        for msg in reversed(list(user_messages)):
            if msg.content not in ['[Image]', '[Voice Note]', '[Document Image]', '[Document Audio]']:
                parts.append(f"User reported: {msg.content}")
        
        return "\n".join(parts) if parts else "User reported threat via Telegram conversation"
    
    def get_localized_message(self, session, default_message):
        if not session or not session.language_preference:
            return default_message
        
        lang = session.language_preference.lower()
        
        if 'pidgin' in lang:
            location_msg = "⚠️ This one look like serious matter wey we fit report to police.\n\n📍 Abeg tell me which city and country you dey:\n\n(Example: Lagos, Nigeria)"
            if "Which city and country" in default_message:
                return location_msg
        elif 'swahili' in lang:
            location_msg = "⚠️ Hii inaonekana ni tishio kubwa ambalo linaweza kuripotiwa kwa mamlaka.\n\n📍 Tafadhali niambie uko katika jiji na nchi gani:\n\n(Mfano: Nairobi, Kenya)"
            if "Which city and country" in default_message:
                return location_msg
        
        return default_message
    
    def get_localized_safety_message(self, session):
        default_msg = "🛡️ I've stopped all current processes. You're safe here.\n\nIf you're in immediate danger, please contact local emergency services.\n\nType /start when you're ready to continue."
        
        if not session or not session.language_preference:
            return default_msg
        
        lang = session.language_preference.lower()
        
        if 'pidgin' in lang:
            return "🛡️ I don stop everything. You safe here.\n\nIf you dey danger, abeg call police or emergency number.\n\nType /start when you ready make we continue."
        elif 'swahili' in lang:
            return "🛡️ Nimesimamisha michakato yote. Uko salama hapa.\n\nIkiwa uko hatarini, tafadhali wasiliana na huduma za dharura.\n\nAndika /start utakapokuwa tayari kuendelea."
        
        return default_msg
    
    def handle_photo(self, chat_id, photos, username, caption=None, session=None):
        analyzing_msg = "🔍 Analyzing your screenshot..."
        if session:
            self.save_message(session, 'assistant', analyzing_msg, 'text')
        self.send_message(chat_id, analyzing_msg)
        
        largest_photo = max(photos, key=lambda p: p.get('file_size', 0))
        file_id = largest_photo.get('file_id')
        
        image_path, mime_type = self.download_file(file_id)
        
        if image_path:
            try:
                # Open with 'rb' to provide a file-like object
                with open(image_path, 'rb') as f:
                    # Wrap in Django File object
                    django_file = File(f, name=os.path.basename(image_path))
                    
                    location_hint = session.last_detected_location if session else None
                    
                    result = report_processor.process_image_report(
                        image_file=django_file,
                        source="telegram",
                        reporter_handle=f"@{username}",
                        additional_text=caption,
                        location_hint=location_hint
                    )
                
                self.send_result(chat_id, result, session)
            finally:
                # Clean up temp file
                if os.path.exists(image_path):
                    os.unlink(image_path)
        else:
            self.send_message(chat_id, "❌ Sorry, I couldn't download the image. Please try again.")
    
    def handle_voice(self, chat_id, voice_data, username, session=None):
        analyzing_msg = "🔍 Analyzing your voice note..."
        if session:
            self.save_message(session, 'assistant', analyzing_msg, 'text')
        self.send_message(chat_id, analyzing_msg)
        
        file_id = voice_data.get('file_id')
        audio_path, mime_type = self.download_file(file_id)
        
        if audio_path:
            try:
                with open(audio_path, 'rb') as f:
                    django_file = File(f, name=os.path.basename(audio_path))
                    
                    location_hint = session.last_detected_location if session else None
                    
                    result = report_processor.process_audio_report(
                        audio_file=django_file,
                        source="telegram",
                        reporter_handle=f"@{username}",
                        location_hint=location_hint
                    )
                
                self.send_result(chat_id, result, session)
            finally:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
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
            # Step 1: Get File Path
            response = requests.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={'file_id': file_id},
                timeout=30
            )
            response.raise_for_status()
            file_info = response.json().get('result', {})
            file_path = file_info.get('file_path')
            
            if file_path:
                # Step 2: Stream Download to Temp File
                file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                
                # Determine extension
                ext = os.path.splitext(file_path)[1]
                if not ext:
                    ext = '.bin'
                
                # Create temp file
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
                os.close(tmp_fd)
                
                with requests.get(file_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    mime_type = r.headers.get('content-type', 'application/octet-stream')
                    with open(tmp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                return tmp_path, mime_type
                
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            # Clean up if partial file exists
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
        return None, None
    
    def send_result(self, chat_id, result, session=None):
        if session:
            session.refresh_from_db()
            if session.is_cancelled():
                logger.info(f"Skipping result send for chat {chat_id} - session was cancelled")
                return
        
        case_id = result.get('case_id', 'N/A')[:8]
        
        if session:
            summary = result.get('summary', 'Analysis complete')
            action = result.get('action', 'advise')
            response_content = f"[{action.upper()}] Case {case_id}: {summary}"
            self.save_message(session, 'assistant', response_content, 'text')
        
        if result.get('action') == 'report':
            partner_name = result.get('partner_name', 'Support Partner')
            partner_email = result.get('partner_email', '')
            
            partner_info = ""
            if partner_name:
                partner_info = f"\n\n📧 *Sent To:*\n{partner_name}"
                if partner_email:
                    partner_info += f"\n_{partner_email}_"
            
            msg = f"""🚨 *HIGH RISK DETECTED*

📋 *Case ID:* `{case_id}`
⚠️ *Risk Score:* {result.get('risk_score', 'N/A')}/10

*Summary:* {result.get('summary', 'Threat detected')}

✅ *Action Taken:* Your report has been forwarded to the appropriate support partner.{partner_info}

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


class PartnerView(View):
    """Partnership page with inquiry form"""
    def get(self, request):
        from partners.constants import AFRICAN_COUNTRIES_BY_REGION
        return render(request, 'intake/partner.html', {
            "african_countries_by_region": AFRICAN_COUNTRIES_BY_REGION,
        })
    
    @method_decorator(form_ratelimit)
    def post(self, request):
        """Handle partnership inquiry form submission"""
        from partners.constants import AFRICAN_COUNTRIES, AFRICAN_COUNTRIES_BY_REGION

        org_name = request.POST.get('organization_name', '').strip()
        contact_name = request.POST.get('contact_name', '').strip()
        email = request.POST.get('email', '').strip()
        country = request.POST.get('country', '').strip()
        partnership_type = request.POST.get('partnership_type', '').strip()
        org_type = request.POST.get('org_type', '').strip()
        message = request.POST.get('message', '').strip()
        
        # Validate Turnstile
        from utils.captcha import validate_turnstile
        token = request.POST.get('cf-turnstile-response')
        is_valid, error_msg = validate_turnstile(token, request.META.get('REMOTE_ADDR'))
        
        if not is_valid:
            return render(request, 'intake/partner.html', {
                'error': error_msg,
                "african_countries_by_region": AFRICAN_COUNTRIES_BY_REGION,
            })
        
        # Basic validation
        if not all([org_name, contact_name, email, country, partnership_type, org_type]):
            return render(request, 'intake/partner.html', {
                'error': 'Please fill in all required fields.',
                "african_countries_by_region": AFRICAN_COUNTRIES_BY_REGION,
            })

        if country not in AFRICAN_COUNTRIES:
            return render(request, 'intake/partner.html', {
                'error': 'Please select a valid African country from the list.',
                "african_countries_by_region": AFRICAN_COUNTRIES_BY_REGION,
            })
        
        # Log the inquiry
        logger.info(f"Partnership inquiry from {org_name} ({email}) - {partnership_type}")
        
        # Send email to Admin (escape HTML to prevent XSS)
        subject = f"New Partner Inquiry: {escape(org_name)}"
        html_content = f"""
        <h3>New Partnership Inquiry</h3>
        <p><strong>Organization:</strong> {escape(org_name)}</p>
        <p><strong>Type:</strong> {escape(org_type)}</p>
        <p><strong>Contact:</strong> {escape(contact_name)}</p>
        <p><strong>Email:</strong> {escape(email)}</p>
        <p><strong>Country:</strong> {escape(country)}</p>
        <p><strong>Partnership Interest:</strong> {escape(partnership_type)}</p>
        <p><strong>Message:</strong></p>
        <p>{escape(message)}</p>
        """
        
        payload = {
            "sender": {"name": "Imara Web System", "email": settings.BREVO_SENDER_EMAIL},
            "to": [{"email": settings.ADMIN_NOTIFICATION_EMAIL}],
            "replyTo": {"email": email, "name": contact_name},
            "subject": subject,
            "htmlContent": html_content
        }
        
        send_email_task(payload)
        
        return render(request, 'intake/partner.html', {
            'success': True,
            "african_countries_by_region": AFRICAN_COUNTRIES_BY_REGION,
        })


def consent_view(request):
    """User consent and data protection page"""
    return render(request, 'intake/consent.html')


def policies_view(request):
    """Reporting policies page"""
    return render(request, 'intake/policies.html')


class ContactView(View):
    """Contact Us page"""
    def get(self, request):
        form = ContactForm()
        return render(request, 'intake/contact.html', {'form': form})
    
    @method_decorator(form_ratelimit)
    def post(self, request):
        # Validate Turnstile first
        from utils.captcha import validate_turnstile
        token = request.POST.get('cf-turnstile-response')
        is_valid, error_msg = validate_turnstile(token, request.META.get('REMOTE_ADDR'))
        
        if not is_valid:
            form = ContactForm(request.POST)
            return render(request, 'intake/contact.html', {'form': form, 'error': error_msg})
        
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            
            # Send email to Admin (escape HTML to prevent XSS)
            email_subject = f"Contact Form: {escape(subject)}"
            html_content = f"""
            <h3>New Contact Form Message</h3>
            <p><strong>Name:</strong> {escape(name)}</p>
            <p><strong>Email:</strong> {escape(email)}</p>
            <p><strong>Subject:</strong> {escape(subject)}</p>
            <p><strong>Message:</strong></p>
            <p>{escape(message)}</p>
            """
            
            payload = {
                "sender": {"name": "Imara Web System", "email": settings.BREVO_SENDER_EMAIL},
                "to": [{"email": settings.ADMIN_NOTIFICATION_EMAIL}],
                "replyTo": {"email": email, "name": name},
                "subject": email_subject,
                "htmlContent": html_content
            }
            
            send_email_task(payload)
            
            return render(request, 'intake/contact.html', {'form': ContactForm(), 'success': True})
        
        return render(request, 'intake/contact.html', {'form': form})

