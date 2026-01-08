# Audit Report: Intake App (`intake/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `intake/views.py`, `intake/services.py`, `intake/forms.py`, `intake/urls.py`, `intake/tests.py`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 0 |
| 🟠 HIGH | 3 |
| 🟡 MEDIUM | 6 |
| 🔵 LOW | 4 |

This is the **largest app** (1,200+ lines) handling web forms, Telegram bot, and all report processing. Well-architected overall, but has **duplicate code**, **memory concerns**, and **imports inside methods**.

---

## 🟠 HIGH Priority Issues

### 1. Duplicate Line in views.py (Lines 515-516)

**Current Code:**
```python
file_id = voice_data.get('file_id')
file_id = voice_data.get('file_id')  # <- DUPLICATE!
audio_path, mime_type = self.download_file(file_id)
```

**Problem:** Exact duplicate line. Harmless but indicates copy-paste error.

**Fix:** Delete line 516.

---

### 2. ThreadPoolExecutor in Class Definition (views.py line 160)

**Current Code:**
```python
@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="telegram_worker")
```

**Problems:**
1. **Class-level attribute** - All instances share the same executor
2. **Never shutdown** - Threads persist forever
3. **Memory concern** for 1GB RAM with 4 workers + 4 from dispatch service

**Fix - Reduce workers and add shutdown:**
```python
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="telegram_worker")

@classmethod
def shutdown_executor(cls):
    cls._executor.shutdown(wait=True)
```

---

### 3. Imports Inside Methods (Multiple Locations)

**Locations in views.py:**
- Line 181: `from django.db import close_old_connections`
- Line 191-192: `from triage.models import ChatSession`
- Line 202: `from triage.models import ChatMessage`
- Line 221, 241: `import requests`
- Line 258: `import requests`
- Line 401-402: `from triage.decision_engine import DecisionEngine`
- Line 547: `import requests`
- Line 650, 682: `import requests`

**Problem:** 
1. Imports are slow (even cached lookups have overhead)
2. Repeated `import requests` 6+ times is wasteful
3. Violates Python style guidelines

**Fix - Move all to top of file:**
```python
import requests  # Once at top
from django.db import close_old_connections
from triage.models import ChatSession, ChatMessage
from triage.decision_engine import DecisionEngine
```

---

## 🟡 MEDIUM Priority Issues

### 4. Large Service Worker Embedded in Python (lines 34-103)

**Current:** 70 lines of JavaScript inside Python string:
```python
def serviceworker_view(request):
    sw_content = """
const CACHE_NAME = 'imara-pwa-v1';
...
"""
```

**Problem:** 
1. Hard to maintain/debug JavaScript in Python
2. No syntax highlighting or linting
3. Duplicates static/js/serviceworker.js

**Fix:** Serve from static file instead:
```python
def serviceworker_view(request):
    from django.http import FileResponse
    sw_path = settings.BASE_DIR / 'static/js/serviceworker.js'
    return FileResponse(open(sw_path, 'rb'), content_type='application/javascript')
```

---

### 5. Image Loaded Fully into Memory (services.py lines 164-165)

**Current Code:**
```python
image_file.seek(0)
image_bytes = image_file.read()  # Full file in memory
```

**Problem:** With 1GB RAM, large images (5-10MB) could exhaust memory.

**Note:** The code acknowledges this with comments (lines 156-162). The AI client unfortunately requires bytes. Consider future refactor to stream.

---

### 6. No Rate Limiting on Telegram Webhook

**Current:** `TelegramWebhookView` accepts unlimited POST requests.

**Risk:** 
- Telegram replay attacks
- DoS via webhook flooding
- AI API quota exhaustion

**Fix - Add simple rate limiting:**
```python
from functools import lru_cache
from time import time

@lru_cache(maxsize=100)
def is_rate_limited(chat_id: str, window=5) -> bool:
    # Simple in-memory rate limit: 1 request per 5 seconds per user
    return None  # Implement with timestamp tracking
```

---

### 7. Missing Telegram Request Verification

**Current Code (line 158-178):**
```python
@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            # ... no verification of request origin
```

**Problem:** Anyone can POST fake updates to the webhook. Telegram sends a secret header that should be verified.

**Fix - Verify secret token:**
```python
def post(self, request):
    secret_token = os.environ.get('TELEGRAM_WEBHOOK_SECRET')
    if secret_token:
        header_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        if header_token != secret_token:
            return HttpResponse(status=403)
```

---

### 8. Empty models.py

**Current (models.py):**
```python
from django.db import models
```

**Action:** Delete file entirely - no models in this app.

---

### 9. Empty admin.py

**Current (admin.py):**
```python
from django.contrib import admin
```

**Action:** Delete file entirely - no admin needed.

---

## 🔵 LOW Priority Issues

### 10. Test Coverage is Basic

**Current tests only cover:**
- Form validation (text-only)
- Form validation (no evidence)
- Report page loads

**Missing tests:**
- TelegramWebhookView
- ReportProcessor methods
- Image/audio report processing
- Callback handling
- Safe word detection
- Localization

---

### 11. Keep-alive Endpoint Name Inconsistency

**URLs:**
```python
path('ping/', views.keep_alive, name='keep_alive'),
```

**Tech docs:** References `/keep-alive/` endpoint

**Fix:** Align documentation with actual URL.

---

### 12. Unused Import (views.py)

**Line 5:**
```python
import hmac
```

**Usage:** Never used anywhere in the file.

**Action:** Remove.

---

### 13. Unused Import (views.py)

**Line 14:**
```python
import shutil
```

**Usage:** Never used anywhere.

**Action:** Remove.

---

## ✅ What's Already Good

1. **Excellent Telegram integration** - Full bot with commands, photos, voice, callbacks
2. **Safe word detection** - Multiple words including local languages
3. **Localized messages** - Pidgin and Swahili support
4. **Session context** - 10-message history for coherent AI responses
5. **Cancellation system** - Timestamp-based to handle race conditions
6. **Chunked file download** - Uses streaming (line 582)
7. **Temp file cleanup** - Files are unlinked after use
8. **Connection management** - `close_old_connections()` in async tasks
9. **Good form validation** - Requires at least one evidence type
10. **Consent checkbox** - Legal requirement for reporting

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Remove duplicate line 516 | Low | 🟠 Bug |
| 2 | Move imports to top | Low | 🟠 Perf |
| 3 | Reduce ThreadPoolExecutor workers | Low | 🟠 Memory |
| 4 | Add webhook verification | Medium | 🟡 Security |
| 5 | Move service worker to static | Low | 🟡 Maint |
| 6 | Delete empty files | Low | 🔵 Cleanup |
| 7 | Remove unused imports | Low | 🔵 Cleanup |

---

## Files Connected (Dependencies)

**Internal:**
- `triage/decision_engine.py` - AI analysis
- `triage/models.py` - ChatSession, ChatMessage
- `cases/models.py` - IncidentReport, EvidenceAsset
- `directory/models.py` - AuthorityContact
- `dispatch/service.py` - Email dispatch
- `dispatch/models.py` - DispatchLog

**Templates:**
- `templates/intake/index.html`
- `templates/intake/report_form.html`
- `templates/intake/result.html`
- `templates/offline.html`

**External:**
- Telegram API (api.telegram.org)
- Groq API (via triage)
- Gemini API (via triage)
- Brevo API (via dispatch)

---

## URL Endpoints

| Path | View | Method | Purpose |
|------|------|--------|---------|
| `/` | HomeView | GET | Landing page |
| `/report/` | ReportFormView | GET/POST | Web report form |
| `/result/` | ResultView | GET | Redirects to report |
| `/offline/` | offline_view | GET | PWA offline page |
| `/serviceworker.js` | serviceworker_view | GET | PWA service worker |
| `/webhook/telegram/` | TelegramWebhookView | POST | Telegram bot webhook |
| `/health/` | health_check | GET | Health check |
| `/ping/` | keep_alive | GET | Keep-alive |

---

## Code Metrics

| File | Lines | Functions/Methods | Classes |
|------|-------|-------------------|---------|
| views.py | 709 | 25+ | 4 |
| services.py | 459 | 7 | 1 |
| forms.py | 63 | 1 | 1 |
| urls.py | 14 | 0 | 0 |
| tests.py | 34 | 3 | 2 |
| **Total** | **1,279** | **36+** | **8** |
