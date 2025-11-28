# Project Imara - Digital Bodyguard

## Overview
Project Imara ("Strong" in Swahili) is a Zero-UI Digital Bodyguard designed to protect women and girls from online gender-based violence (OGBV). The platform uses hybrid AI (Groq for text/audio + Gemini for images) to analyze threats and routes them appropriately.

## Tech Stack
- **Framework**: Django 5.0 (Python 3.11)
- **Database**: PostgreSQL (Neon) with SQLite fallback
- **AI Services**: Groq (Llama-3.3-70b for text, Whisper for audio), Google Gemini 2.5 Flash (image OCR)
- **Email**: Brevo Transactional API
- **Interfaces**: Web Form (PWA) + Telegram Bot
- **Static Files**: WhiteNoise
- **Production Server**: Gunicorn

## Environment Variables Required
| Variable | Purpose |
|----------|---------|
| DATABASE_URL | PostgreSQL connection string |
| GROQ_API_KEY | Groq AI API key |
| GEMINI_API_KEY | Google Gemini API key |
| BREVO_API_KEY | Brevo email API key |
| BREVO_SENDER_EMAIL | Verified sender email in Brevo (optional) |
| TELEGRAM_BOT_TOKEN | Telegram bot token |
| SESSION_SECRET | Django secret key |

## Project Structure
```
/
├── imara/              # Django project settings
│   ├── settings.py     # Main configuration
│   ├── urls.py         # Root URL routing
│   └── wsgi.py         # WSGI application
├── cases/              # Incident reports & evidence
├── directory/          # Authority contacts database
├── dispatch/           # Email dispatch service (Brevo)
├── triage/             # AI analysis engine (Groq + Gemini)
├── intake/             # Web & Telegram interfaces
├── templates/          # HTML templates
├── static/             # CSS, JS, images
└── media/              # User uploads
```

## Running Commands
```bash
# Development
uv run python manage.py runserver 0.0.0.0:5000

# Production (Render)
gunicorn --bind 0.0.0.0:$PORT --workers 2 imara.wsgi:application

# Database
uv run python manage.py migrate
uv run python manage.py seed_authorities
uv run python manage.py createsuperuser
uv run python manage.py collectstatic
```

## Deployment to Render
1. Connect your GitHub repository to Render
2. Set environment variables in Render dashboard:
   - SESSION_SECRET (generate a secure key)
   - DATABASE_URL (from Neon or Render PostgreSQL)
   - GROQ_API_KEY
   - GEMINI_API_KEY
   - BREVO_API_KEY
   - BREVO_SENDER_EMAIL (your verified Brevo sender email)
   - TELEGRAM_BOT_TOKEN
   - DEBUG=False
3. The render.yaml file configures the build and start commands automatically

## Recent Changes
- Updated database configuration to use dj-database-url for better Render compatibility
- Added 19 real African helplines (Kenya, Uganda, Tanzania, South Africa, Nigeria, Ghana, Rwanda)
- Added Render deployment configuration (render.yaml, Procfile)
- Added Render domains to CSRF trusted origins
