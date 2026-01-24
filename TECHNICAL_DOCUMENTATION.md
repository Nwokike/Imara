# Project Imara - Zero-UI Digital Bodyguard

## Overview
**A project of Kiri Research Labs**

Project Imara is a "Zero-UI Digital Bodyguard" platform that protects women and girls from online violence across Africa. The platform:
- Analyzes threats via AI (text, voice, image)
- Provides instant safety advice
- Automatically escalates high-risk cases to verified support partners
- Works through existing apps (Telegram, Web PWA) without requiring downloads
- Serves as an educational platform for online safety

flowchart TD
  userWeb[UserWebBrowser]
  userTelegram[UserTelegram]
  nginx[Nginx]
  django["DjangoApp (imara)"]
  intake["intake app"]
  triage["triage app"]
  cases["cases app"]
  dispatchApp["dispatch app"]
  partnersApp["partners app"]
  publicationsApp["publications app"]
  db[(DB: SQLite/Postgres)]
  r2[(CloudflareR2 Storage)]
  brevo[(Brevo Email API)]
  groq[(Groq API)]
  gemini[(Gemini API)]

  userWeb --> nginx --> django
  userTelegram --> django

  django --> intake
  intake --> triage
  intake --> cases
  intake --> dispatchApp
  intake --> partnersApp
  intake --> publicationsApp

  triage --> groq
  triage --> gemini
  cases --> db
  triage --> db
  dispatchApp --> db
  partnersApp --> db
  publicationsApp --> db

  cases --> r2
  django --> brevo


## API Endpoints
- `/` - Landing page
- `/report/` - Web report form
- `/webhook/telegram/` - Telegram bot webhook
- `/webhook/meta/` - Meta (Facebook/Instagram) webhook
- `/health/` - Health check
- `/ping/` - Keep-alive endpoint

## Environment Variables

### Required for Production Boot

The following environment variables are **required** for a safe production deployment:

**Django Core:**
- `SECRET_KEY`: Django secret key (required, will raise `ImproperlyConfigured` if missing in production)
- `DEBUG=False`: Must be `False` in production
- `ALLOWED_HOSTS`: Comma-separated list (e.g. `imara.africa,www.imara.africa`). If not set, falls back to a default list with a warning.

**Database:**
- `DATABASE_URL`: PostgreSQL connection string (format: `postgresql://user:pass@host:5432/db?sslmode=require`). If not set, SQLite is used as fallback (acceptable for dev/low-traffic only).

**AI Services:**
- `GROQ_API_KEY`: For AI text analysis (required)
- `GEMINI_API_KEY`: For image/audio analysis (required)

**Email Dispatch:**
- `BREVO_API_KEY`: For sending forensic alerts (required)
- `BREVO_SENDER_EMAIL`: Sender email address (defaults to `imara-alerts@projectimara.org`)
- `ADMIN_NOTIFICATION_EMAIL`: Admin notification recipient (defaults to `projectimarahq@gmail.com`)

**Storage:**
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`: Cloudflare R2 storage (required for media files)
- `R2_BACKUP_BUCKET_NAME`: R2 bucket for database backups (required if using SQLite backup task)
- `R2_ENDPOINT_URL`: R2 endpoint URL

**Security:**
- `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`: Cloudflare Turnstile CAPTCHA (required for form protection)

### Optional

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_SECRET_TOKEN`: Only if using Telegram integration
- `META_APP_SECRET`, `META_PAGE_ACCESS_TOKEN`, `META_VERIFY_TOKEN`: Only if using Facebook Messenger/Instagram
- `GROQ_MODEL`, `GEMINI_MODEL`: Model selection (defaults provided)
- `R2_CUSTOM_DOMAIN`: CDN domain for media files
- `PGDATABASE`, `PGUSER`, etc.: For CLI tools only, not used by Django

### Runtime Constraints & Limits

**Memory & Performance (1GB VM):**
- Max upload size: 10MB (`DATA_UPLOAD_MAX_MEMORY_SIZE`)
- File upload threshold: 5MB before temp file (`FILE_UPLOAD_MAX_MEMORY_SIZE`)
- Recommended Gunicorn workers: 2 workers, 2 threads
- Recommended Huey workers: 1-2 workers to avoid SQLite contention

**Data Retention:**
- Chat sessions/messages and user feedback are automatically pruned via a Huey periodic task:
  - `triage.tasks.triage_retention_cleanup_task` (runs daily at 04:15)
  - Configurable via env:
    - `TRIAGE_MESSAGE_RETENTION_DAYS` (default 90)
    - `TRIAGE_SESSION_RETENTION_DAYS` (default 90)
    - `TRIAGE_FEEDBACK_RETENTION_DAYS` (default 365)
- Incident reports: Permanent (forensic integrity)
- Evidence assets: Permanent (linked to incidents)

**Database:**
- SQLite acceptable for low-traffic deployments (< 100 concurrent users)
- Postgres recommended for production scale
- Backup task runs only for SQLite (Postgres requires separate `pg_dump` process)

### Operational Runbook (Production)

**Health checks**
- App: `GET /health/`
- Keep-alive: `GET /ping/`

**Services (systemd)**
- Web: `sudo systemctl status imara`
- Worker: `sudo systemctl status huey`
- Proxy: `sudo systemctl status nginx`

**Common failure modes**
- AI provider down (Groq/Gemini):
  - User still receives a safe fallback response; monitor logs for sustained provider errors.
- Turnstile misconfigured/outage:
  - Public forms (report/contact/partner/comments) will reject submissions in production.
- Brevo down / API key issues:
  - Dispatch tasks will mark `DispatchLog` as failed; partner notifications may be delayed.
- SQLite contention / disk pressure:
  - Reduce workers, ensure log rotation, and move to Postgres if write contention increases.

**Backup & restore (SQLite)**
- Backups are created daily by `dispatch.tasks.backup_database_task` and uploaded to R2 under the `db-backups/` prefix.
- Restore steps (high level):
  - Stop services: `sudo systemctl stop imara huey`
  - Download the desired backup from R2 to the server
  - Replace `db.sqlite3` with the backup file
  - Run migrations: `uv run python manage.py migrate`
  - Start services: `sudo systemctl start huey imara`

## Running Locally
```bash
# 1. Install dependencies
uv sync  # or pip install -e .

# 2. Setup environment
cp .env.example .env

# 3. Initialize database
python manage.py migrate
python manage.py seed_partners

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
7. **Partner notes**: Partner investigators add notes in `IncidentReport.ai_analysis['partner_notes']` (keeps notes attached to the case without a separate model)

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

## Meta Platform Integration (Facebook Messenger & Instagram)

### Webhook Configuration
- **Endpoint**: `https://imara.africa/webhook/meta/`
- **Verification Token**: Set in `META_VERIFY_TOKEN` environment variable
- **Signature Verification**: Uses `X-Hub-Signature-256` header with `META_APP_SECRET` for security

### Supported Events
- **Messenger**: `messages`, `messaging_postbacks`, `messaging_referrals`
- **Instagram**: `messages`, `comments`, `live_comments`, `message_edit`, `message_reactions`, `messaging_handover`, `messaging_referral`, `messaging_seen`, `standby`

### App Review Process
To move from Development to Live mode:

1. **Required Permissions**:
   - `pages_messaging` (Messenger)
   - Instagram messaging scopes (for Instagram integration)

2. **Test Plan**:
   - Demonstrate safe word functionality ("STOP")
   - Show location gathering for high-risk cases
   - Test image/audio processing
   - Verify forensic alert dispatch to partners
   - Test feedback collection

3. **Environment Variables** (Production):
   - `META_APP_SECRET`: App secret from Meta Developer Console
   - `META_PAGE_ACCESS_TOKEN`: Page access token with messaging permissions
   - `META_VERIFY_TOKEN`: Custom verification token (must match webhook config)

### Instagram-Specific Behavior
- Instagram messages and comments are processed similarly to Messenger
- Uses same `ChatSession` and `ChatMessage` models
- Reuses same triage and reporting logic via `ReportProcessor`
