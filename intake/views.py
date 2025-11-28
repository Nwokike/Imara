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


@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            logger.info(f"Received Telegram update: {data}")
            
            self.process_update(data)
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return HttpResponse(status=200)
    
    def process_update(self, update):
        import requests
        
        message = update.get('message')
        if not message:
            return
        
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        username = user.get('username') or user.get('first_name') or 'Anonymous'
        
        text = message.get('text')
        photo = message.get('photo')
        voice = message.get('voice')
        audio = message.get('audio')
        document = message.get('document')
        
        forwarded = message.get('forward_from') or message.get('forward_from_chat')
        
        if text and text.startswith('/'):
            self.handle_command(chat_id, text, username)
            return
        
        if photo:
            self.handle_photo(chat_id, photo, username, message.get('caption'))
        elif voice or audio:
            voice_data = voice or audio
            self.handle_voice(chat_id, voice_data, username)
        elif text:
            self.handle_text(chat_id, text, username)
        elif document:
            mime_type = document.get('mime_type', '')
            if mime_type.startswith('image/'):
                self.handle_document_image(chat_id, document, username, message.get('caption'))
            elif mime_type.startswith('audio/'):
                self.handle_document_audio(chat_id, document, username)
            else:
                self.send_message(chat_id, "I can analyze text messages, screenshots, and voice notes. Please forward one of these to me.")
        else:
            self.send_message(chat_id, "Forward me any abusive message, screenshot, or voice note and I'll analyze it for you.")
    
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
    
    def handle_text(self, chat_id, text, username):
        self.send_message(chat_id, "🔍 Analyzing your message...")
        
        result = report_processor.process_text_report(
            text=text,
            source="telegram",
            reporter_handle=f"@{username}"
        )
        
        self.send_result(chat_id, result)
    
    def handle_photo(self, chat_id, photos, username, caption=None):
        self.send_message(chat_id, "🔍 Analyzing your screenshot...")
        
        largest_photo = max(photos, key=lambda p: p.get('file_size', 0))
        file_id = largest_photo.get('file_id')
        
        image_bytes, mime_type = self.download_file(file_id)
        
        if image_bytes:
            from io import BytesIO
            from django.core.files.uploadedfile import InMemoryUploadedFile
            
            file_obj = BytesIO(image_bytes)
            file_obj.seek(0)
            
            result = report_processor.process_image_report(
                image_file=file_obj,
                source="telegram",
                reporter_handle=f"@{username}",
                additional_text=caption
            )
            
            self.send_result(chat_id, result)
        else:
            self.send_message(chat_id, "❌ Sorry, I couldn't download the image. Please try again.")
    
    def handle_voice(self, chat_id, voice_data, username):
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
            
            result = report_processor.process_audio_report(
                audio_file=audio_file,
                source="telegram",
                reporter_handle=f"@{username}"
            )
            
            import os
            os.unlink(tmp_path)
            
            self.send_result(chat_id, result)
        else:
            self.send_message(chat_id, "❌ Sorry, I couldn't download the voice note. Please try again.")
    
    def handle_document_image(self, chat_id, document, username, caption=None):
        self.handle_photo(chat_id, [document], username, caption)
    
    def handle_document_audio(self, chat_id, document, username):
        self.handle_voice(chat_id, document, username)
    
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
    
    def send_result(self, chat_id, result):
        if result.get('action') == 'report':
            msg = f"""🚨 *HIGH RISK DETECTED*

📋 *Case ID:* `{result.get('case_id', 'N/A')[:8]}`
⚠️ *Risk Score:* {result.get('risk_score', 'N/A')}/10

*Summary:* {result.get('summary', 'Threat detected')}

✅ *Action Taken:* Your report has been forwarded to the appropriate authorities.

Stay safe. We're here to protect you. 🛡️"""
        else:
            msg = f"""✅ *Analysis Complete*

📋 *Case ID:* `{result.get('case_id', 'N/A')[:8]}`
📊 *Risk Score:* {result.get('risk_score', 'N/A')}/10

*Summary:* {result.get('summary', 'Content analyzed')}

💡 *Advice:*
{result.get('advice', 'Stay safe and document any further incidents.')}

You're not alone. We're here to help. 🛡️"""
        
        self.send_message(chat_id, msg)
    
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
