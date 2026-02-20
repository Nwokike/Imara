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
    import time
    version = int(time.time())
    sw_content = f"""
const CACHE_NAME = 'imara-pwa-v{version}';
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
            location = (form.cleaned_data.get('location') or '').strip() or None
            
            if image:
                result = report_processor.process_image_report(
                    image_file=image,
                    source="web",
                    reporter_email=email,
                    reporter_name=name or None,
                    additional_text=text,
                    location_hint=location
                )
            elif audio:
                result = report_processor.process_audio_report(
                    audio_file=audio,
                    source="web",
                    reporter_email=email,
                    reporter_name=name or None,
                    location_hint=location
                )
            elif text:
                result = report_processor.process_text_report(
                    text=text,
                    source="web",
                    reporter_email=email,
                    reporter_name=name or None,
                    location_hint=location
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
    def post(self, request):
        try:
            secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            expected_token = os.environ.get('TELEGRAM_SECRET_TOKEN')
            
            if expected_token and secret_token != expected_token:
                logger.warning(f"Invalid Telegram secret token: {secret_token}")
                return HttpResponse(status=403)

            data = json.loads(request.body)
            logger.debug(f"Received Telegram update: {data}")
            
            # Use persistent Huey task for processing
            from triage.tasks import process_telegram_update_task
            process_telegram_update_task(data)
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return HttpResponse(status=200)

def health_check(request):
