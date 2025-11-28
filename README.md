# Project Imara

![homepage](https://imgur.com/Fcfcp9g.png)


> **"Imara"** means *"Strong"* in Swahili

A Zero-UI Digital Bodyguard that protects women and girls from online gender-based violence (OGBV).

## What It Does

1. **Report** - Submit abusive messages, screenshots, or voice notes
2. **AI Analysis** - Hybrid AI (Groq + Gemini) analyzes threat level (1-10)
3. **Action** - Low risk gets advice; high risk is automatically reported to authorities

## Features

- **Hybrid AI Engine** - Groq Llama-3.3-70b for text/audio, Gemini 2.5 Flash for images
- **Automatic Escalation** - High-risk threats (7+) sent directly to relevant authorities
- **User Confirmation** - Email confirmation when reports are escalated
- **Authority Network** - 19+ helplines across 7 African countries
- **Chain of Custody** - SHA-256 hashing for forensic integrity
- **PWA Ready** - Install as app, works offline

## Platforms

| Platform | Status |
|----------|--------|
| Web Portal | Active |
| Telegram Bot | Active |
| WhatsApp | Coming Soon |
| Instagram | Coming Soon |
| Facebook | Coming Soon |
| X (Twitter) | Coming Soon |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Seed authority contacts
python manage.py seed_authorities

# Start server
python manage.py runserver 0.0.0.0:5000
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `GROQ_API_KEY` | Groq AI API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `BREVO_API_KEY` | Brevo email API key |
| `BREVO_SENDER_EMAIL` | Verified sender email |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `SESSION_SECRET` | Django secret key |

## Tech Stack

- **Framework**: Django 5.0
- **Database**: PostgreSQL (Neon)
- **AI**: Groq + Google Gemini
- **Email**: Brevo
- **Static**: WhiteNoise

---

*Power Hacks 2025 Hackathon Project*
