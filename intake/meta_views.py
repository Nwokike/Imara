"""
Meta Platform (Facebook Messenger / Instagram) Webhook Handler
"""
import json
import hmac
import hashlib
import logging
from django.conf import settings
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from utils.ratelimit import telegram_webhook_ratelimit

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(telegram_webhook_ratelimit, name='post')
class MetaWebhookView(View):
    """
    Unified Webhook for Facebook Messenger and Instagram.
    """
    
    def get(self, request, *args, **kwargs):
        """
        VERIFICATION HANDSHAKE
        Meta sends a GET request to verify we own this server.
        """
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode and token:
            if mode == 'subscribe' and token == settings.META_VERIFY_TOKEN:
                logger.info("Meta Webhook Verified Successfully!")
                return HttpResponse(challenge, status=200)
            else:
                logger.warning("Meta Webhook Verification Failed: Invalid Token")
                return HttpResponse('Forbidden', status=403)
        
        return HttpResponse('Bad Request', status=400)
    
    def post(self, request, *args, **kwargs):
        """
        MESSAGE RECEIVER
        Meta sends POST requests here when users message the bot.
        """
        # Step 1: Verify X-Hub-Signature-256
        signature = request.headers.get('X-Hub-Signature-256', '')
        if not self._verify_signature(request.body, signature):
            logger.warning("Meta Webhook: Invalid signature")
            return HttpResponse('Forbidden', status=403)
        
        try:
            body = json.loads(request.body.decode('utf-8'))
            logger.debug(f"Meta Webhook received: {body}")
            
            object_type = body.get('object')
            
            # Handle Messenger (Page) events
            if object_type == 'page':
                self._process_page_events(body)
                return HttpResponse('EVENT_RECEIVED', status=200)
            
            # Handle Instagram events
            elif object_type == 'instagram':
                self._process_instagram_events(body)
                return HttpResponse('EVENT_RECEIVED', status=200)
            
            else:
                logger.info(f"Meta Webhook: Unknown object type '{object_type}'")
                return HttpResponse('Not Found', status=404)
                
        except json.JSONDecodeError:
            logger.error("Meta Webhook: Invalid JSON payload")
            return HttpResponse('Bad Request', status=400)
        except Exception as e:
            logger.error(f"Meta Webhook Error: {str(e)}")
            return HttpResponse('EVENT_RECEIVED', status=200) 
    
    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the X-Hub-Signature-256 header using the App Secret.
        """
        app_secret = settings.META_APP_SECRET
        if not app_secret:
            logger.warning("META_APP_SECRET not configured")
            return True 
        
        if not signature:
            return False
        
        if not signature.startswith('sha256='):
            return False
        
        expected_signature = signature[7:]
        computed_hash = hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_hash, expected_signature)
    
    def _process_page_events(self, body: dict):
        """Process Facebook Messenger (Page) webhook events."""
        for entry in body.get('entry', []):
            messaging_events = entry.get('messaging', [])
            for event in messaging_events:
                # Use persistent Django 6 Native task
                from triage.tasks import process_meta_event_task
                process_meta_event_task.enqueue(event, 'messenger')
    
    def _process_instagram_events(self, body: dict):
        """Process Instagram webhook events."""
        for entry in body.get('entry', []):
            messaging_events = entry.get('messaging', [])
            for event in messaging_events:
                # Use persistent Django 6 Native task
                from triage.tasks import process_meta_event_task
                process_meta_event_task.enqueue(event, 'instagram')
