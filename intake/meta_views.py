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
            return HttpResponse('EVENT_RECEIVED', status=200)  # Always return 200 to avoid retries
    
    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the X-Hub-Signature-256 header using the App Secret.
        
        This is CRITICAL for security - ensures requests actually come from Meta.
        """
        app_secret = settings.META_APP_SECRET
        if not app_secret:
            logger.warning("META_APP_SECRET not configured - skipping signature verification")
            return True  # Allow in dev mode, but log warning
        
        if not signature:
            return False
        
        # Signature format: "sha256=<hex_digest>"
        if not signature.startswith('sha256='):
            return False
        
        expected_signature = signature[7:]  # Remove 'sha256=' prefix
        
        # Compute HMAC-SHA256
        computed_hash = hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
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
    
    def _handle_messaging_event(self, event: dict, platform: str):
        """
        Handle a single messaging event from Meta.
        
        This runs in a background thread to avoid webhook timeouts.
        """
        try:
            close_old_connections()
            
            sender_id = event.get('sender', {}).get('id')
            if not sender_id:
                return
            
            # Get or create session
            session = self._get_or_create_session(sender_id, platform)
            
            # Handle different event types
            if 'message' in event:
                message = event['message']
                
                # Check for quick reply payload (feedback)
                if message.get('quick_reply'):
                    self._handle_quick_reply(sender_id, message['quick_reply'], session)
                    return
                
                # Handle text message
                if 'text' in message:
                    self._handle_text_message(sender_id, message['text'], session, platform)
                
                # Handle image attachments
                elif message.get('attachments'):
                    for attachment in message['attachments']:
                        if attachment.get('type') == 'image':
                            self._handle_image(sender_id, attachment, session, platform)
                        elif attachment.get('type') == 'audio':
                            self._handle_audio(sender_id, attachment, session, platform)
                
            elif 'postback' in event:
                # Handle postback from buttons
                self._handle_postback(sender_id, event['postback'], session)
                
        except Exception as e:
            logger.error(f"Meta message handling error: {e}")
        finally:
            close_old_connections()
    
    def _get_or_create_session(self, sender_id: str, platform: str) -> ChatSession:
        """Get or create a chat session for this user."""
        session, created = ChatSession.objects.get_or_create(
            chat_id=sender_id,
            defaults={'platform': platform}
        )
        if session.platform != platform:
            session.platform = platform
            session.save()
        return session
    
    def _save_message(self, session: ChatSession, role: str, content: str, message_type: str = 'text'):
        """Save a message to the session history."""
        ChatMessage.objects.create(
            session=session,
            role=role,
            content=content[:2000],
            message_type=message_type
        )
    
    def _check_safe_word(self, text: str) -> bool:
        """Check if message contains a safe word."""
        if not text:
            return False
        text_upper = text.upper().strip()
        return any(safe_word in text_upper for safe_word in SAFE_WORDS)
    
    def _handle_text_message(self, sender_id: str, text: str, session: ChatSession, platform: str):
        """Process a text message from the user."""
        # Check for safe word
        if self._check_safe_word(text):
            session.set_cancelled(seconds=60)
            safety_msg = "🛡️ I've stopped all current processes. You're safe here.\n\nIf you're in immediate danger, please contact local emergency services.\n\nSend 'Hi' when you're ready to continue."
            self._save_message(session, 'assistant', safety_msg)
            meta_messenger.send_text_message(sender_id, safety_msg, platform)
            return
        
        # If we were waiting for location from older flows, store it and continue
        if session.awaiting_location:
            session.last_detected_location = text
            session.awaiting_location = False
            session.pending_report_data = None
            # Also persist into gathered evidence for the conversation engine
            if isinstance(session.gathered_evidence, dict):
                session.gathered_evidence = {**session.gathered_evidence, "location": text}
            session.save()
        
        # Save user message
        self._save_message(session, 'user', text)
        
        # Send typing indicator
        meta_messenger.send_typing_indicator(sender_id)

        # Conversational AI engine (shared with Telegram for consistency)
        from triage.conversation_engine import conversation_engine

        response = conversation_engine.process_message(
            session=session,
            user_message=text,
            message_type='text'
        )

        # Persist state
        session.conversation_state = response.state.value
        if response.gathered_info:
            session.gathered_evidence = {**session.gathered_evidence, **response.gathered_info}
        if response.detected_language:
            session.language_preference = response.detected_language

        # Track required fields bookkeeping (non-blocking)
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
            pass

        session.save()

        # Save assistant response to message history
        self._save_message(session, 'assistant', response.message)

        # Check if cancelled during processing
        session.refresh_from_db()
        if session.is_cancelled():
            return

        # Send response
        meta_messenger.send_text_message(sender_id, response.message, platform)

        # Create case when ready
        if response.should_create_report:
            self._create_and_send_report(sender_id, session, platform, response.gathered_info)
        elif response.is_low_risk:
            session.conversation_state = 'IDLE'
            session.gathered_evidence = {}
            session.save()

    def _create_and_send_report(self, sender_id: str, session: ChatSession, platform: str, gathered_info: dict):
        """Create a formal report after confirmation in conversational flow."""
        evidence_summary = gathered_info.get('evidence_summary', '')
        location = gathered_info.get('location') or session.last_detected_location or 'Unknown'
        risk_score = gathered_info.get('risk_score', 7)
        reporter_name = (gathered_info.get('reporter_name') or '').strip() or None
        contact_preference = (gathered_info.get('contact_preference') or '').strip() or None
        incident_description = (gathered_info.get('incident_description') or evidence_summary or '').strip()

        # Guardrail: if still missing critical fields, ask explicitly instead of creating a case
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
            self._save_message(session, 'assistant', prompt)
            meta_messenger.send_text_message(sender_id, prompt, platform)
            return

        # Store location for future use
        if location and location != 'Unknown':
            session.last_detected_location = location
            session.save()

        # Build a report text payload from conversation history + gathered fields
        parts = []
        if reporter_name:
            parts.append(f"Reporter Name: {reporter_name}")
        if contact_preference:
            parts.append(f"Contact Preference: {contact_preference}")
        if incident_description:
            parts.append(f"Incident Description: {incident_description}")
        if gathered_info.get('threat_type'):
            parts.append(f"Threat Type: {gathered_info.get('threat_type')}")
        if gathered_info.get('perpetrator_info'):
            parts.append(f"Perpetrator: {gathered_info.get('perpetrator_info')}")
        # Include last few user messages
        user_messages = session.messages.filter(role='user').order_by('-created_at')[:5]
        for msg in reversed(list(user_messages)):
            if msg.content not in ['[Image]', '[Voice Note]', '[Document Image]', '[Document Audio]']:
                parts.append(f"User reported: {msg.content}")
        report_text = "\n".join([p for p in parts if p]) or "User reported threat via Meta conversation"

        result = report_processor.process_text_report(
            text=report_text,
            source=platform,
            reporter_handle=f"meta:{sender_id}",
            location_hint=location,
            reporter_name=reporter_name,
            contact_preference=contact_preference,
            perpetrator_info=gathered_info.get('perpetrator_info') or None,
        )

        session.conversation_state = 'IDLE'
        session.gathered_evidence = {}
        session.save()

        self._send_result(sender_id, result, session, platform)
    
    def _handle_location_response(self, sender_id: str, text: str, session: ChatSession, platform: str):
        """Handle a location response from the user."""
        self._save_message(session, 'user', text)
        
        session.last_detected_location = text
        pending_data = session.pending_report_data or {}
        session.awaiting_location = False
        session.pending_report_data = None
        session.save()
        
        original_text = pending_data.get('text', '')
        if original_text:
            confirmation_msg = f"📍 Got it - {text}. Processing your report now..."
            self._save_message(session, 'assistant', confirmation_msg)
            meta_messenger.send_text_message(sender_id, confirmation_msg, platform)
            
            result = report_processor.process_text_report(
                text=original_text,
                source=platform,
                reporter_handle=f"meta:{sender_id}",
                location_hint=text
            )
            
            self._send_result(sender_id, result, session, platform)
        else:
            saved_msg = f"📍 Location saved as {text}. You can now send me content to analyze."
            self._save_message(session, 'assistant', saved_msg)
            meta_messenger.send_text_message(sender_id, saved_msg, platform)
    
    def _handle_image(self, sender_id: str, attachment: dict, session: ChatSession, platform: str):
        """Process an image attachment."""
        self._save_message(session, 'user', '[Image]', 'image')
        
        # Send processing message
        meta_messenger.send_typing_indicator(sender_id)
        meta_messenger.send_text_message(sender_id, "🔍 Analyzing your screenshot...", platform)
        
        image_url = attachment.get('payload', {}).get('url')
        if not image_url:
            meta_messenger.send_text_message(
                sender_id, 
                "❌ Sorry, I couldn't download the image. Please try again.",
                platform
            )
            return
        
        # Download and process image
        try:
            import requests
            response = requests.get(image_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Save to temp file
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(tmp_fd)
            
            with open(tmp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            try:
                with open(tmp_path, 'rb') as f:
                    django_file = File(f, name='meta_image.jpg')
                    location_hint = session.last_detected_location
                    
                    result = report_processor.process_image_report(
                        image_file=django_file,
                        source=platform,
                        reporter_handle=f"meta:{sender_id}",
                        location_hint=location_hint
                    )
                
                self._send_result(sender_id, result, session, platform)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            logger.error(f"Failed to process Meta image: {e}")
            meta_messenger.send_text_message(
                sender_id,
                "❌ Sorry, I couldn't process that image. Please try again.",
                platform
            )
    
    def _handle_audio(self, sender_id: str, attachment: dict, session: ChatSession, platform: str):
        """Process an audio attachment."""
        self._save_message(session, 'user', '[Voice Note]', 'voice')
        
        meta_messenger.send_typing_indicator(sender_id)
        meta_messenger.send_text_message(sender_id, "🔍 Analyzing your voice note...", platform)
        
        audio_url = attachment.get('payload', {}).get('url')
        if not audio_url:
            meta_messenger.send_text_message(
                sender_id,
                "❌ Sorry, I couldn't download the audio. Please try again.",
                platform
            )
            return
        
        try:
            import requests
            response = requests.get(audio_url, timeout=60, stream=True)
            response.raise_for_status()
            
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mp4')
            os.close(tmp_fd)
            
            with open(tmp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            try:
                with open(tmp_path, 'rb') as f:
                    django_file = File(f, name='meta_audio.mp4')
                    location_hint = session.last_detected_location
                    
                    result = report_processor.process_audio_report(
                        audio_file=django_file,
                        source=platform,
                        reporter_handle=f"meta:{sender_id}",
                        location_hint=location_hint
                    )
                
                self._send_result(sender_id, result, session, platform)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            logger.error(f"Failed to process Meta audio: {e}")
            meta_messenger.send_text_message(
                sender_id,
                "❌ Sorry, I couldn't process that audio. Please try again.",
                platform
            )
    
    def _handle_quick_reply(self, sender_id: str, quick_reply: dict, session: ChatSession):
        """Handle quick reply (feedback) from user."""
        from triage.models import UserFeedback
        
        payload = quick_reply.get('payload', '')
        if payload.startswith('feedback_'):
            parts = payload.split('_')
            rating = parts[1] if len(parts) > 1 else 'unknown'
            case_id = parts[2] if len(parts) > 2 else None
            
            UserFeedback.objects.create(
                chat_id=sender_id,
                case_id=case_id,
                rating=rating
            )
            
            if rating == 'helpful':
                meta_messenger.send_text_message(sender_id, "Thank you for your feedback! We're glad we could help.")
            else:
                meta_messenger.send_text_message(sender_id, "Thank you for your feedback. We'll work to improve our service.")
    
    def _handle_postback(self, sender_id: str, postback: dict, session: ChatSession):
        """Handle postback from buttons."""
        payload = postback.get('payload', '')
        logger.info(f"Meta postback from {sender_id}: {payload}")
        # Handle different postback types as needed
    
    def _send_result(self, sender_id: str, result: dict, session: ChatSession, platform: str):
        """Send analysis result to user with feedback buttons."""
        session.refresh_from_db()
        if session.is_cancelled():
            logger.info(f"Skipping result for {sender_id} - session cancelled")
            return
        
        case_id = result.get('case_id', 'N/A')[:8]
        
        # Save assistant response
        summary = result.get('summary', 'Analysis complete')
        action = result.get('action', 'advise')
        self._save_message(session, 'assistant', f"[{action.upper()}] Case {case_id}: {summary}")
        
        if result.get('action') == 'report':
            partner_name = result.get('partner_name', 'Support Partner')
            partner_email = result.get('partner_email', '')
            
            partner_info = ""
            if partner_name:
                partner_info = f"\n\n📧 Sent To:\n{partner_name}"
                if partner_email:
                    partner_info += f"\n{partner_email}"
            
            msg = f"""🚨 HIGH RISK DETECTED

📋 Case ID: {case_id}
⚠️ Risk Score: {result.get('risk_score', 'N/A')}/10

Summary: {result.get('summary', 'Threat detected')}

✅ Action Taken: Your report has been forwarded to the appropriate support partner.{partner_info}

⚡ Safety Reminder: Consider deleting this conversation if someone might check your phone. Type STOP anytime if you feel unsafe.

Keep this Case ID for your records. Stay safe. 🛡️"""
        else:
            msg = f"""✅ Analysis Complete

📋 Case ID: {case_id}
📊 Risk Score: {result.get('risk_score', 'N/A')}/10

Summary: {result.get('summary', 'Content analyzed')}

💡 Advice:
{result.get('advice', 'Stay safe and document any further incidents.')}

You're not alone. We're here to help. 🛡️"""
        
        # Send with feedback buttons
        feedback_buttons = [
            {"title": "👍 Helpful", "payload": f"feedback_helpful_{case_id}"},
            {"title": "👎 Not Helpful", "payload": f"feedback_not_helpful_{case_id}"}
        ]
        
        success = meta_messenger.send_message_with_buttons(sender_id, msg, feedback_buttons, platform)
        if not success:
            # Fallback to plain text if buttons fail
            meta_messenger.send_text_message(sender_id, msg, platform)
