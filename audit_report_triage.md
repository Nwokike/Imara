# Audit Report: Triage App (`triage/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `triage/decision_engine.py`, `triage/clients/groq_client.py`, `triage/clients/gemini_client.py`, `triage/models.py`, `triage/tests.py`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 0 |
| 🟠 HIGH | 3 |
| 🟡 MEDIUM | 5 |
| 🔵 LOW | 3 |

This is the **AI engine** of the platform. The implementation is solid with good fallback handling, but has **thread safety concerns**, **inconsistent action handling**, and **model deprecation risks**.

---

## 🟠 HIGH Priority Issues

### 1. Gemini Client Missing ASK_LOCATION Action (Line 90-91)

**Current Code (gemini_client.py):**
```python
if data['action'] not in ['ADVISE', 'REPORT']:
    data['action'] = 'ADVISE'
```

**Problem:** Groq client supports `ASK_LOCATION` action (for high-risk threats without location), but Gemini doesn't:
- **Groq (line 190-191):** `if analysis_data['action'] not in ['ADVISE', 'REPORT', 'ASK_LOCATION']`
- **Gemini (line 90-91):** `if data['action'] not in ['ADVISE', 'REPORT']`

**Impact:** Image analysis can never trigger ASK_LOCATION, even for high-risk images without location.

**Fix:**
```python
if data['action'] not in ['ADVISE', 'REPORT', 'ASK_LOCATION']:
    data['action'] = 'ADVISE'
```

---

### 2. Singleton Pattern Not Thread-Safe (Multiple Files)

**Affected Files:**
- `groq_client.py` (lines 31-37)
- `gemini_client.py` (lines 29-35)

**Current Code:**
```python
_instance = None
_initialized = False

def __new__(cls):
    if cls._instance is None:  # Race condition here!
        cls._instance = super().__new__(cls)
    return cls._instance
```

**Problem:** Race condition if two threads call the constructor simultaneously.

**Fix:**
```python
import threading

_lock = threading.Lock()

def __new__(cls):
    with cls._lock:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
    return cls._instance
```

---

### 3. ChatSession Model - Import Inside Method (Lines 39-40, 45-46)

**Current Code:**
```python
def is_cancelled(self):
    from django.utils import timezone  # Import inside method
    ...

def set_cancelled(self, seconds=30):
    from django.utils import timezone  # Repeated import
    from datetime import timedelta
```

**Problem:** Imports inside methods are slower (lookup every call) and violate convention.

**Fix - Move to top of file:**
```python
from django.db import models
from django.utils import timezone
from datetime import timedelta
```

---

## 🟡 MEDIUM Priority Issues

### 4. Model Name Hardcoded (groq_client.py line 160)

**Current Code:**
```python
"model": "llama-3.3-70b-versatile",
```

**Problem:** Model name is hardcoded. When Groq releases newer models (like GPT-5 era), you'll need to change code.

**Fix - Make configurable:**
```python
import os
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
```

---

### 5. Model Name Hardcoded (gemini_client.py line 170)

**Current Code:**
```python
model="gemini-2.5-flash",
```

**Same issue:** Hardcoded model name.

**Fix:**
```python
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
```

---

### 6. Gemini Client Lacks Retry Error Handling for Specific Errors

**Groq client (lines 83-90)** handles 429 rate limiting specially:
```python
if response.status_code == 429:
    # Longer delay for rate limits
```

**Gemini client (lines 191-200)** catches generic exceptions only:
```python
except Exception as e:
    last_error = e
    logger.warning(...)
```

**Fix:** Add specific handling for Gemini rate limits and quota errors.

---

### 7. Global Singleton at Module Level (decision_engine.py line 205)

**Current Code:**
```python
decision_engine = DecisionEngine()
```

**Problem:** Creates instance at import time, before Django is fully configured.

**Recommendation:** Use lazy initialization or Django's apps.py ready() method.

---

### 8. Test Coverage Gaps

**Current tests only cover:**
- Text analysis (high/low risk)

**Missing tests:**
- Image analysis
- Audio transcription
- ASK_LOCATION action
- Fallback behavior
- Error handling
- ChatSession model methods
- UserFeedback model

---

## 🔵 LOW Priority Issues

### 9. Empty views.py and admin.py

**triage/views.py:** Empty boilerplate
**triage/admin.py:** Only contains `from django.contrib import admin`

**Action:** Delete views.py, add admin registration:
```python
# admin.py
from django.contrib import admin
from .models import ChatSession, ChatMessage, UserFeedback

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['chat_id', 'username', 'platform', 'last_detected_location', 'created_at']
    list_filter = ['platform', 'awaiting_location']
    search_fields = ['chat_id', 'username']
```

---

### 10. Whisper Model Could Be Configurable

**Current (groq_client.py line 217):**
```python
"model": "whisper-large-v3",
```

**Recommendation:** Same as above - make environment variable.

---

### 11. ChatSession.get_recent_messages Inefficiency (line 23)

**Current Code:**
```python
def get_recent_messages(self, limit=10):
    return list(self.messages.order_by('-created_at')[:limit])[::-1]
```

**Problem:** Fetches in reverse, slices, then reverses again in Python.

**More efficient:**
```python
def get_recent_messages(self, limit=10):
    return list(self.messages.order_by('created_at').reverse()[:limit])
# Or using subquery for true efficiency
```

---

## ✅ What's Already Good

1. **Excellent fallback system** - Works even without API keys
2. **Pydantic validation** - Strong response typing
3. **Retry logic with exponential backoff** - Resilient to transient failures
4. **Conversation context** - Last 10 messages for coherent responses
5. **Multi-modal support** - Text, image, audio analysis
6. **Good test mocking** - Tests use proper mocks
7. **Lazy client initialization** - DecisionEngine uses properties
8. **db_index on chat_id** - Efficient lookups
9. **Safe word cancellation** - Timestamp-based to handle race conditions

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add ASK_LOCATION to Gemini | Low | 🟠 Feature |
| 2 | Add thread-safe singleton locks | Low | 🟠 Stability |
| 3 | Move imports to top level | Low | 🟠 Perf |
| 4 | Make model names configurable | Low | 🟡 Maint |
| 5 | Add admin registrations | Low | 🔵 UX |
| 6 | Expand test coverage | Medium | 🔵 Quality |

---

## Files Connected (Dependencies)

- **intake/views.py** - Uses DecisionEngine for analysis
- **intake/services.py** - Creates ChatSession/ChatMessage
- **dispatch/service.py** - Receives results from triage
- **cases/models.py** - Stores TriageResult in IncidentReport

---

## AI Model Dependencies

| Service | Model | Purpose | Cost Tier |
|---------|-------|---------|-----------|
| Groq | llama-3.3-70b-versatile | Text threat analysis | Free tier |
| Groq | whisper-large-v3 | Audio transcription | Free tier |
| Gemini | gemini-2.5-flash | Image OCR + analysis | Free tier |

**Note:** All models are on free tiers - watch for quota limits in production.

---

## Code Metrics

| File | Lines | Classes | Methods |
|------|-------|---------|---------|
| decision_engine.py | 206 | 2 | 8 |
| groq_client.py | 280 | 2 | 5 |
| gemini_client.py | 230 | 2 | 6 |
| models.py | 96 | 3 | 6 |
| **Total** | **812** | **9** | **25** |
