# Project Imara - Development Progress Report

## Document Version: 1.0
## Date: November 28, 2025
## Status: In Development

---

## Executive Summary

Project Imara ("Strong" in Swahili) is a Zero-UI Digital Bodyguard designed to protect women and girls from online gender-based violence (OGBV). This document details the implementation progress, architectural decisions, and remaining work.

---

## 1. What Has Been Completed

### 1.1 Project Infrastructure (Developer 1 Scope)

#### Django Project Setup
- **Framework**: Django 5.0 with Python 3.11
- **Database**: PostgreSQL (Neon) configured via DATABASE_URL
- **Web Server**: Gunicorn with 2 workers on port 5000
- **Static Files**: WhiteNoise for production-ready static serving
- **Project Structure**: 5 Django apps created (cases, directory, dispatch, intake, triage)

#### Database Models Implemented

**IncidentReport** (cases/models.py)
- UUID-based case_id for unique identification
- Source tracking (telegram, web, whatsapp, instagram)
- Reporter handle and email storage
- Text fields: original_text, transcribed_text, extracted_text
- AI analysis JSON storage
- Risk score (1-10) and action (pending/advise/report)
- Location detection field
- Chain of custody hash (SHA-256)
- Dispatch tracking (timestamp and recipient)

**EvidenceAsset** (cases/models.py)
- Linked to IncidentReport via ForeignKey
- Asset type classification (text, image, audio, video)
- File storage with date-based organization
- Derived text storage (OCR/transcription results)
- SHA-256 digest for evidence integrity

**AuthorityContact** (directory/models.py)
- Agency name and contact details
- Jurisdiction level (city, state, country, regional)
- Tags array for categorization (Cybercrime, Domestic Violence, etc.)
- Priority-based routing
- Location-based lookup method

**DispatchLog** (dispatch/models.py)
- Incident and authority linkage
- Email dispatch tracking
- Brevo message ID storage
- Status tracking (pending, sent, failed, bounced)

#### AI Integration (Hybrid Intelligence)

**Groq Client** (triage/clients/groq_client.py)
- Integration with Groq API (Llama-3.3-70b-versatile)
- Text threat analysis with structured JSON output
- Audio transcription via Whisper API
- Pydantic model for response validation

**Gemini Client** (triage/clients/gemini_client.py)
- Integration with Google Gemini 2.5 Flash
- Image/screenshot OCR and analysis
- Multimodal threat assessment
- Support for both file path and bytes input

**Decision Engine** (triage/decision_engine.py)
- Unified interface for all content types
- Modality detection (text, image, audio)
- ADVISE vs REPORT routing logic
- Fallback handling for errors

### 1.2 Web Interface (Developer 2 Scope)

#### Web Sentinel Landing Page (templates/intake/index.html)
- Professional hero section with shield branding
- "Report Online Violence Securely" headline
- Platform availability grid:
  - Telegram Bot: Active
  - Web Portal: Active
  - WhatsApp: Coming Soon
  - Instagram: Coming Soon
- How It Works section (3-step process)
- Threat detection categories display
- Call-to-action for reporting

#### Report Form (templates/intake/report_form.html)
- Text message/description textarea
- Screenshot upload (image files)
- Voice note upload (audio files)
- Optional email for updates
- Consent checkbox for authority reporting
- Loading state during submission

#### Result Page (templates/intake/result.html)
- Conditional display based on action (REPORT/ADVISE)
- Case ID display
- Risk score visualization
- Summary and advice display
- Extracted text preview
- Next steps guidance

#### Brevo Email Dispatch (dispatch/service.py)
- Brevo Transactional API integration
- Professional forensic email HTML template
- Email content includes:
  - Official header with Project Imara branding
  - Risk level banner (color-coded)
  - Case metadata (ID, timestamp, source, location)
  - AI threat summary
  - Evidence content section
  - Chain of custody hash
  - Action required section
- Threaded async dispatch capability

### 1.3 Telegram Bot Integration

**Webhook Handler** (intake/views.py)
- TelegramWebhookView for incoming updates
- Command handling (/start, /help, /status)
- Text message processing
- Photo/image handling with file download
- Voice note handling
- Document processing (images and audio)
- Result formatting and response

### 1.4 Database Seeding

**Authority Contacts Seeded** (10 entries):
1. Nigeria Police Force - Cybercrime Unit (National)
2. Lagos State Domestic Violence Unit
3. Kenya National Police - Gender Desk
4. Nairobi Women Safety Initiative
5. South Africa Police Service - SAPS
6. Ghana Domestic Violence Victim Support
7. Accra Women Rights Coalition
8. Uganda Police - Child and Family Protection
9. Tanzania Women Legal Aid Centre
10. Pan-African Women Safety Network (Regional fallback)

### 1.5 Admin Interface
- IncidentReport admin with fieldsets
- EvidenceAsset admin
- AuthorityContact admin with inline editing
- DispatchLog admin

---

## 2. What Needs Improvement (Architect Review)

### 2.1 Critical Issues Identified

#### AI Client Robustness
- [ ] Add network retry/backoff for API failures
- [ ] Graceful handling when env vars missing (don't crash at import)
- [ ] Schema validation for AI responses
- [ ] Handle non-JSON or malformed responses

#### Chain of Custody
- [ ] Ensure EvidenceAsset hash is computed before dispatch
- [ ] Link asset hashes to IncidentReport chain properly
- [ ] Complete tamper-proof audit trail

#### Email Dispatch
- [ ] Implement actual async threading (currently synchronous)
- [ ] Update DispatchLog status after send attempts
- [ ] Handle staging environment (no API key)

#### Report Processing
- [ ] Complete audio report processing implementation
- [ ] Cleanup temp files after processing
- [ ] Ensure ADVISE path saves advice in response

#### Telegram Webhook
- [ ] Implement signature verification (HMAC)
- [ ] Handle missing message fields gracefully
- [ ] Full integration with DecisionEngine

#### Web UI
- [ ] Ensure all context keys are supplied to templates
- [ ] Handle file upload edge cases

### 2.2 Recommendations for Next Steps

1. **Harden External Services**: Add retry logic, timeouts, and proper error handling
2. **Complete End-to-End Flows**: Ensure all report modalities work reliably
3. **Fix Dispatch Integration**: Make threading actually async, update logs
4. **Telegram Verification**: Add security for webhook
5. **Template Context**: Ensure consistent data for UI

---

## 3. Technical Specifications

### 3.1 Environment Variables Required
| Variable | Purpose | Status |
|----------|---------|--------|
| DATABASE_URL | PostgreSQL connection | Configured |
| GROQ_API_KEY | Groq AI API | Configured |
| GEMINI_API_KEY | Google Gemini API | Configured |
| BREVO_API_KEY | Brevo email service | Configured |
| TELEGRAM_BOT_TOKEN | Telegram bot | Configured |
| SESSION_SECRET | Django secret key | Configured |

### 3.2 API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| / | GET | Landing page |
| /report/ | GET, POST | Report form |
| /result/ | GET | Analysis results |
| /webhook/telegram/ | POST | Telegram webhook |
| /health/ | GET | Health check |
| /ping/ | GET | Keep-alive |
| /admin/ | GET | Django admin |

### 3.3 AI Decision Logic
```
Risk Score 1-3: Low risk (insults) → ADVISE
Risk Score 4-6: Moderate (harassment) → ADVISE
Risk Score 7-10: High risk (threats/doxing) → REPORT
```

---

## 4. File Structure

```
/home/runner/workspace/
├── imara/                      # Django project config
│   ├── settings.py             # Main settings
│   ├── urls.py                 # URL routing
│   └── wsgi.py                 # WSGI application
├── cases/                      # Incident tracking
│   ├── models.py               # IncidentReport, EvidenceAsset
│   ├── admin.py                # Admin registration
│   └── migrations/
├── directory/                  # Authority contacts
│   ├── models.py               # AuthorityContact
│   ├── admin.py                # Admin registration
│   └── management/commands/    # seed_authorities
├── dispatch/                   # Email dispatch
│   ├── models.py               # DispatchLog
│   ├── service.py              # BrevoDispatcher
│   └── admin.py
├── triage/                     # AI analysis
│   ├── clients/
│   │   ├── groq_client.py      # Text AI
│   │   └── gemini_client.py    # Vision AI
│   └── decision_engine.py      # Routing logic
├── intake/                     # User interfaces
│   ├── views.py                # Web & Telegram handlers
│   ├── services.py             # ReportProcessor
│   ├── forms.py                # Report form
│   └── urls.py                 # URL patterns
├── templates/                  # HTML templates
│   ├── base.html               # Base template
│   └── intake/
│       ├── index.html          # Landing page
│       ├── report_form.html    # Report form
│       └── result.html         # Results page
├── static/                     # Static assets
├── media/                      # User uploads
├── manage.py                   # Django management
├── replit.md                   # Project documentation
└── PROGRESS_REPORT.md          # This document
```

---

## 5. Development Timeline

### Phase 1: Core Backend (Completed)
- Django project scaffolding
- Database models and migrations
- AI client integration (Groq + Gemini)
- Decision engine logic

### Phase 2: Web Interface (Completed)
- Landing page design
- Report form implementation
- Result display pages
- Brevo email templates

### Phase 3: Hardening (In Progress)
- Error handling improvements
- Async dispatch implementation
- Chain of custody fixes
- Telegram security

### Phase 4: Testing & Demo (Pending)
- End-to-end testing
- Demo scenario scripting
- Performance optimization

---

## 6. Demo Scenarios (Per Specification)

### Scenario 1: Low Risk (ADVISE)
**Input**: "He called me stupid."
**Expected Result**: 
- Risk Score: 2-3
- Action: ADVISE
- Response: Blocking tips and mental health resources
- No email sent

### Scenario 2: High Risk (REPORT)
**Input**: "He posted my address on X."
**Expected Result**:
- Risk Score: 8-9
- Action: REPORT
- Response: Confirmation of escalation
- Forensic email sent to authorities

---

## 7. Next Actions (Priority Order)

1. Fix AI client error handling and env var checks
2. Implement proper async email dispatch with status updates
3. Complete chain of custody hash linking
4. Add Telegram webhook signature verification
5. Ensure all template contexts are properly populated
6. Test end-to-end flows for all modalities
7. Create admin superuser for dashboard access

---

*Document prepared by AI Development Agent*
*Project Imara - Power Hacks 2025 Hackathon*
