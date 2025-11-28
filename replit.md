# Project Imara - Digital Bodyguard

## Overview
Zero-UI Digital Bodyguard protecting women and girls from online gender-based violence (OGBV). Uses hybrid AI (Groq + Gemini) to analyze threats and route high-risk cases to authorities.

## Tech Stack
- **Framework**: Django 5.0 (Python 3.11)
- **Database**: PostgreSQL (Neon)
- **AI**: Groq (Llama-3.3-70b for text, Whisper for audio), Google Gemini 2.5 Flash (images)
- **Email**: Brevo Transactional API
- **Interfaces**: Web Form (PWA) + Telegram Bot
- **Static Files**: WhiteNoise

## Environment Variables
| Variable | Purpose |
|----------|---------|
| DATABASE_URL | PostgreSQL connection |
| GROQ_API_KEY | Groq AI API |
| GEMINI_API_KEY | Google Gemini API |
| BREVO_API_KEY | Brevo email API |
| BREVO_SENDER_EMAIL | Verified sender email |
| TELEGRAM_BOT_TOKEN | Telegram bot token |
| SESSION_SECRET | Django secret key |

## Project Structure
```
imara/          # Django settings
cases/          # Incident reports & evidence
directory/      # Authority contacts (19+ helplines)
dispatch/       # Email dispatch (Brevo)
triage/         # AI analysis (Groq + Gemini)
intake/         # Web & Telegram interfaces
templates/      # HTML templates
static/         # CSS, JS, images
```

## Commands
```bash
uv run python manage.py runserver 0.0.0.0:5000  # Dev
uv run python manage.py migrate                  # DB
uv run python manage.py seed_authorities         # Seed
```

## Key Features
- **Risk Scoring**: 1-10 scale, ADVISE (1-6) vs REPORT (7-10)
- **Auto Dispatch**: High-risk reports sent to authorities via Brevo
- **User Confirmation**: Email sent to user when report is escalated
- **Telegram Details**: Authority info shown in bot response
- **Chain of Custody**: SHA-256 hashing for forensic integrity
- **PWA**: Installable, offline support

## Recent Changes
- Mobile-optimized UI with responsive design
- Dark mode toggle always visible (no hamburger menu)
- Email now required on web form
- User receives confirmation email when report is escalated
- Telegram shows authority details for escalated reports
- 8 platform cards (Web, Telegram active; 6 coming soon)
- Improved dark mode colors and contrast
