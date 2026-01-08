# Project Imara - Zero-UI Digital Bodyguard

## Overview
**A project of Kiri Research Labs**

Project Imara is a "Zero-UI Digital Bodyguard" platform that protects women and girls from online violence across Africa. The platform:
- Analyzes threats via AI (text, voice, image)
- Provides instant safety advice
- Automatically reports high-risk cases to authorities
- Works through existing apps (Telegram, Web PWA) without requiring downloads
- Serves as an educational platform for online safety

## Recent Changes (November 29, 2025)

### Bug Fixes
- Fixed session message storage to correctly save assistant responses with role="assistant"
- Fixed ASK_LOCATION flow to properly pass location_hint when user provides location
- Fixed safe word detection to fully clear both awaiting_location and pending_report_data
- Added user feedback confirmation message when location is received

### Frontend Modernization
- Redesigned hero section with mission-focused messaging
- Updated navigation with education-first approach
- Stats show: 24/7 availability, AI-powered analysis, 7 African countries
- Removed repetitive "Imara means Strong" branding
- Footer updated with simplified messaging

### Smart Conversational Logic (Telegram)
- Session context tracking (ChatSession model)
- Message history storage (ChatMessage model)
- ASK_LOCATION action when threat is high but location unknown
- Safe word detection ("IMARA STOP", "STOP", "CANCEL", "HELP ME", "EXIT", "EMERGENCY")
- Feedback buttons on analysis results
- Safety warnings on report confirmations
- Dialect/language detection for African languages

### Database Models Added
- `triage.ChatSession`: Tracks user sessions with location, language, pending state
- `triage.ChatMessage`: Stores conversation history (last 10 messages for context)
- `triage.UserFeedback`: Collects helpful/not helpful ratings

## Project Structure
```
imara/
├── imara/          # Django settings and configuration
├── intake/         # Main app: views, forms, services for report processing
├── triage/         # AI analysis: Groq client, decision engine, models
├── cases/          # Incident reports and evidence storage
├── directory/      # Authority contacts database
├── dispatch/       # Email dispatch to authorities via Brevo
├── templates/      # HTML templates (base.html, intake/)
├── static/         # CSS, JS, images
└── test/           # Test cases
```

## Key Files
- `triage/clients/groq_client.py`: AI threat analysis with Groq API
- `triage/decision_engine.py`: Orchestrates AI analysis (text, image, audio)
- `intake/views.py`: Web and Telegram webhook handlers
- `intake/services.py`: Report processing logic
- `templates/intake/index.html`: Landing page
- `static/css/styles.css`: All styling

## API Endpoints
- `/` - Landing page
- `/report/` - Web report form
- `/telegram/webhook/` - Telegram bot webhook
- `/health/` - Health check
- `/keep-alive/` - Keep-alive endpoint

## Environment Variables
- `GROQ_API_KEY`: For AI text analysis
- `GOOGLE_AI_API_KEY`: For image/audio analysis (Gemini)
- `BREVO_API_KEY`: For sending emails to authorities
- `TELEGRAM_BOT_TOKEN`: For Telegram bot
- `DATABASE_URL`: PostgreSQL connection

## Running Locally
```bash
# 1. Install dependencies
uv sync  # or pip install -e .

# 2. Setup environment
cp .env.example .env

# 3. Initialize database
python manage.py migrate
python manage.py seed_authorities

# 4. Run server
python manage.py runserver
```

## Key Design Decisions
1. **Zero-UI approach**: Works inside existing apps, no separate download needed
2. **Session context**: Last 10 messages used for conversation context
3. **ASK_LOCATION**: For high-risk threats without location, bot asks for location before reporting
4. **Safe words**: User can type "STOP" anytime to halt processes
5. **Feedback buttons**: Every analysis result has thumbs up/down buttons
6. **Safety warnings**: High-risk reports include reminder to delete conversation

## Safe Word Race Condition Fix
The safe word feature uses timestamp-based cancellation to handle race conditions:

1. **`cancelled_until` field**: Stores when cancellation expires (60 seconds from trigger)
2. **`is_cancelled()` method**: Checks if `cancelled_until > now`
3. **`set_cancelled(seconds=60)`**: Sets a 60-second cancellation window
4. **Flow**: 
   - User sends high-risk message → Handler A starts processing
   - User sends STOP → `cancelled_until = now + 60 seconds`
   - User sends /start → Command processed, but cancellation NOT cleared
   - Handler A completes → `is_cancelled()` returns True → Response blocked
   - After 60 seconds, cancellation expires naturally

## Localized Messaging
Supports African languages with localized responses:
- **Pidgin**: "STOP! Everything don stop. Your safety na first."
- **Swahili**: "SIMAMA! Kila kitu kimesimama. Usalama wako ndio kwanza."
- **English**: Default for other languages
