# Project Imara - Digital Bodyguard

## Overview
Project Imara ("Strong" in Swahili) is a Zero-UI Digital Bodyguard designed to protect women and girls from online gender-based violence (OGBV). The platform uses hybrid AI (Groq for text/audio + Gemini for images) to analyze threats and routes them appropriately - either providing advice for minor issues or automatically reporting serious threats to authorities via Brevo email.

## Tech Stack
- **Framework**: Django 5.0 (Python 3.11)
- **Database**: PostgreSQL (Neon) with SQLite fallback
- **AI Services**: Groq (Llama-3.3-70b for text, Whisper for audio), Google Gemini 2.5 Flash (image OCR)
- **Email**: Brevo Transactional API
- **Interfaces**: Web Form (PWA) + Telegram Bot
- **Static Files**: WhiteNoise
- **Production Server**: Gunicorn

## Project Structure
```
/
├── imara/              # Django project settings
│   ├── settings.py     # Main configuration
│   ├── urls.py         # Root URL routing
│   └── wsgi.py         # WSGI application
├── cases/              # Incident reports & evidence
│   ├── models.py       # IncidentReport, EvidenceAsset
│   └── admin.py
├── directory/          # Authority contacts database
│   ├── models.py       # AuthorityContact (JSONField for tags)
│   └── management/commands/seed_authorities.py
├── dispatch/           # Email dispatch service
│   ├── models.py       # DispatchLog
│   └── service.py      # BrevoDispatcher (async threading)
├── triage/             # AI analysis engine
│   ├── clients/
│   │   ├── groq_client.py   # Text/audio AI
│   │   └── gemini_client.py # Image/OCR AI
│   └── decision_engine.py   # ADVISE vs REPORT logic
├── intake/             # Web & Telegram interfaces
│   ├── views.py        # HomeView, ReportFormView, TelegramWebhookView
│   ├── services.py     # ReportProcessor
│   └── urls.py
├── templates/          # HTML templates (separated CSS/JS)
│   ├── base.html       # PWA-enabled base template
│   ├── 404.html, 500.html, 403.html, 400.html  # Error pages
│   ├── offline.html    # PWA offline page
│   └── intake/
│       ├── index.html       # Landing page
│       ├── report_form.html # Report submission
│       └── result.html      # Analysis results
├── static/
│   ├── css/styles.css  # All styles (dark mode support)
│   ├── js/main.js      # All JavaScript
│   ├── js/serviceworker.js  # PWA service worker
│   ├── manifest.json   # PWA manifest
│   └── images/         # Logo and PWA icons
└── media/              # User uploads (evidence files)
```

## Environment Variables Required
| Variable | Purpose |
|----------|---------|
| DATABASE_URL | PostgreSQL connection string |
| GROQ_API_KEY | Groq AI API key |
| GEMINI_API_KEY | Google Gemini API key |
| BREVO_API_KEY | Brevo email API key |
| TELEGRAM_BOT_TOKEN | Telegram bot token |
| SESSION_SECRET | Django secret key |

## Key Features
- **AI Triage**: Risk score 1-10, ADVISE (1-6) vs REPORT (7-10)
- **Multi-modal**: Text, screenshots, voice notes
- **Chain of Custody**: SHA-256 hashing on all evidence
- **PWA**: Installable, works offline
- **Dark Mode**: Toggle with brighter purple colors
- **Telegram Bot**: /start, /help, /status commands

## API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| / | GET | Landing page |
| /report/ | GET/POST | Report form |
| /result/ | GET | Analysis results |
| /offline/ | GET | PWA offline page |
| /webhook/telegram/ | POST | Telegram webhook |
| /health/ | GET | Health check |
| /ping/ | GET | Keep-alive |
| /admin/ | GET | Django admin |

## Running Commands
```bash
# Development
python manage.py runserver 0.0.0.0:5000

# Production
gunicorn --bind 0.0.0.0:5000 --workers 2 imara.wsgi:application

# Database
python manage.py migrate
python manage.py seed_authorities
python manage.py createsuperuser
python manage.py collectstatic
```

## User Preferences
- Clean white background with purple (#6B4C9A) branding
- Brighter purple in dark mode (#A78BFA)
- Completely separated HTML/CSS/JS (no inline styles)
- Modern Bootstrap 5.3 design
- User's purple logo integrated

## Recent Changes
- 2025-11-28: Converted ArrayField to JSONField for SQLite compatibility
- 2025-11-28: Added PWA support (manifest.json, service worker, icons)
- 2025-11-28: Created custom error pages (404, 500, 403, 400)
- 2025-11-28: Reduced font sizes to fix "zoomed" appearance
- 2025-11-28: Made purple brighter in dark mode + logo brightness filter
- 2025-11-28: Removed all inline styles from templates
