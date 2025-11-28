# Project Imara - Digital Bodyguard

## Overview
Project Imara (Swahili for "Strong") is a Zero-UI Digital Bodyguard designed to protect women and girls from online gender-based violence (OGBV). The platform uses hybrid AI (Groq + Gemini) to analyze threats and route them appropriately - either providing advice for minor issues or automatically reporting serious threats to authorities.

## Architecture

### Stack
- **Framework**: Django 5.0 (Python 3.11)
- **Database**: PostgreSQL (Neon)
- **Web Server**: Gunicorn with WhiteNoise for static files
- **AI Services**: 
  - Groq (Llama-3.3-70b) for text analysis and audio transcription
  - Google Gemini 2.5 Flash for image/screenshot OCR
- **Email Dispatch**: Brevo (Sendinblue) Transactional API
- **Interfaces**: Web Form + Telegram Bot

### Project Structure
```
/
├── imara/                  # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── cases/                  # Incident reports and evidence models
│   ├── models.py           # IncidentReport, EvidenceAsset
│   └── admin.py
├── directory/              # Authority contacts database
│   ├── models.py           # AuthorityContact
│   └── management/commands/seed_authorities.py
├── dispatch/               # Email dispatch service
│   ├── models.py           # DispatchLog
│   └── service.py          # BrevoDispatcher
├── triage/                 # AI analysis engine
│   ├── clients/
│   │   ├── groq_client.py
│   │   └── gemini_client.py
│   └── decision_engine.py
├── intake/                 # Web and Telegram interfaces
│   ├── views.py            # HomeView, ReportFormView, TelegramWebhookView
│   ├── services.py         # ReportProcessor
│   └── forms.py
├── templates/              # HTML templates
│   ├── base.html
│   └── intake/
│       ├── index.html
│       ├── report_form.html
│       └── result.html
├── static/                 # Static assets
└── media/                  # User uploads
```

## Key Features

### AI Triage System
The decision engine analyzes content and returns:
- `risk_score`: 1-10 scale
- `action`: "ADVISE" (low risk) or "REPORT" (high risk)
- `location`: Extracted from content for routing
- `summary`: Brief threat description
- `advice`: Helpful guidance for low-risk cases

### Threat Classification
**REPORT (risk 7-10)**: Death threats, doxing, blackmail, stalking, revenge porn
**ADVISE (risk 1-6)**: Insults, rude comments, mild harassment

### Evidence Chain of Custody
- SHA-256 hashing of all evidence
- Case ID tracking
- Timestamp and metadata preservation
- Forensic email with verification hash

## Environment Variables
Required secrets:
- `DATABASE_URL` - PostgreSQL connection
- `GROQ_API_KEY` - Groq AI API key
- `GEMINI_API_KEY` - Google Gemini API key
- `BREVO_API_KEY` - Brevo email API key
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `SESSION_SECRET` - Django secret key

## Running the Project

### Development
```bash
python manage.py runserver 0.0.0.0:5000
```

### Production
```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 imara.wsgi:application
```

### Database Commands
```bash
python manage.py migrate
python manage.py seed_authorities
python manage.py createsuperuser
```

## API Endpoints
- `/` - Landing page (Web Sentinel)
- `/report/` - Report abuse form
- `/result/` - Analysis results
- `/webhook/telegram/` - Telegram bot webhook
- `/health/` - Health check endpoint
- `/ping/` - Keep-alive endpoint
- `/admin/` - Django admin panel

## Telegram Bot Commands
- `/start` - Welcome message
- `/help` - Usage instructions
- `/status` - Bot status check

## Recent Changes
- November 28, 2025: Initial implementation
  - Django project setup with PostgreSQL
  - Hybrid AI engine (Groq + Gemini)
  - Web Sentinel landing page
  - Telegram bot integration
  - Brevo email dispatch
  - Authority contacts seeding

## User Preferences
- Zero-cost infrastructure focus (free tiers)
- No placeholders - real implementations only
- Bootstrap 5 for frontend styling
- Professional, legally-formatted email templates
