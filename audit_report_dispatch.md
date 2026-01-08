# Audit Report: Dispatch App (`dispatch/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `dispatch/service.py`, `dispatch/models.py`, `dispatch/admin.py`, `dispatch/tests.py`, `dispatch/views.py`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 1 |
| 🟠 HIGH | 3 |
| 🟡 MEDIUM | 4 |
| 🔵 LOW | 2 |

The dispatch service is **well-architected** with good retry logic and async handling, but contains a **CRITICAL missing import** that will crash the application. Memory concerns exist for the 1GB RAM constraint.

---

## 🔴 CRITICAL Issues

### 1. Missing `os` Import - Application Will Crash (Line 37)

**Current Code (lines 1-9):**
```python
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
import requests
from datetime import datetime
from typing import Optional, Callable
from django.utils import timezone

logger = logging.getLogger(__name__)
```

**Line 37 uses `os` without import:**
```python
self.api_key = os.environ.get('BREVO_API_KEY')  # <- NameError: os not defined
```

**Also line 49:**
```python
self.sender_email = os.environ.get('BREVO_SENDER_EMAIL', 'imara-alerts@projectimara.org')
```

**Fix - Add import:**
```python
import os  # ADD THIS
import logging
import threading
...
```

---

## 🟠 HIGH Priority Issues

### 2. ThreadPoolExecutor Memory Concern for 1GB RAM (Line 35)

**Current Code:**
```python
self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="brevo_dispatch")
```

**Problem:** While max_workers=4 is conservative, each thread still consumes memory. Combined with gunicorn workers, this could exceed RAM limits during traffic spikes.

**Recommendations:**
1. Consider reducing to `max_workers=2` for 1GB RAM
2. Alternative: Use Django-Q or Celery for background tasks (more efficient memory sharing)
3. Monitor thread count in production

---

### 3. Singleton Pattern Issues (Lines 21-27)

**Current Code:**
```python
_instance = None
_initialized = False

def __new__(cls):
    if cls._instance is None:
        cls._instance = super().__new__(cls)
    return cls._instance
```

**Problems:**
1. **Not thread-safe** - Race condition if two threads call `BrevoDispatcher()` simultaneously
2. **No cleanup mechanism** - `_executor` is never shut down gracefully

**Fix - Thread-safe singleton with cleanup:**
```python
_lock = threading.Lock()

def __new__(cls):
    with cls._lock:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
    return cls._instance

def shutdown(self):
    """Call on application shutdown"""
    self._executor.shutdown(wait=True)
```

---

### 4. Global Singleton Initialization at Module Load (Line 526)

**Current Code:**
```python
brevo_dispatcher = BrevoDispatcher()  # Runs on import
```

**Problem:** This runs when the module is imported, before Django is fully configured. In some deployment scenarios, this could cause issues with environment variables not being loaded yet.

**Fix:**
```python
# Remove global instantiation
# brevo_dispatcher = BrevoDispatcher()

# Use lazy initialization via function instead
def get_dispatcher():
    return BrevoDispatcher()
```

---

## 🟡 MEDIUM Priority Issues

### 5. Import Inside Loop (Lines 126-127, 134-135, 148-149)

**Current Code:**
```python
if attempt < MAX_RETRIES - 1:
    import time  # Imported inside loop!
    time.sleep(RETRY_DELAY * (attempt + 1))
```

**Problem:** Import inside loop is inefficient (though Python caches imports, it's still a lookup).

**Fix - Move import to top:**
```python
import time  # At top of file
```

---

### 6. Unused Import (Line 2)

**Current Code:**
```python
import threading
```

**Usage:** Only used implicitly via ThreadPoolExecutor. The explicit `threading` import is unnecessary.

**Action:** Remove unused import.

---

### 7. DispatchLog Not Updated by Service

**Model has fields:**
```python
brevo_message_id = models.CharField(...)
error_message = models.TextField(...)
sent_at = models.DateTimeField(...)
```

**Problem:** The `send_forensic_alert` method returns data but doesn't update the DispatchLog model. The caller must do this.

**Recommendation:** Either:
1. Document that caller must update DispatchLog
2. Add method to update DispatchLog automatically:
```python
def log_dispatch_result(self, dispatch_log: DispatchLog, result: dict):
    if result.get('success'):
        dispatch_log.status = 'sent'
        dispatch_log.brevo_message_id = result.get('message_id')
        dispatch_log.sent_at = timezone.now()
    else:
        dispatch_log.status = 'failed'
        dispatch_log.error_message = result.get('error')
    dispatch_log.save()
```

---

### 8. Empty views.py File

**Current Code:**
```python
from django.shortcuts import render

# Create your views here.
```

**Action:** Delete file entirely—this is a service-only app with no views needed.

---

## 🔵 LOW Priority Issues

### 9. Test Coverage is Minimal

**Current tests (tests.py):**
- Only tests DispatchLog model creation
- No tests for:
  - `BrevoDispatcher.send_forensic_alert()`
  - `send_async()`
  - Retry logic
  - Error handling

**Recommendation:** Add mock-based tests:
```python
from unittest.mock import patch, MagicMock

class BrevoDispatcherTest(TestCase):
    @patch('dispatch.service.requests.post')
    def test_send_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'messageId': '123'}
        # ... test assertion
```

---

### 10. HTML Email Templates Could Be External

**Lines 174-293 and 405-494** contain large HTML strings (hundreds of lines).

**Current:** HTML is embedded in Python code
**Better:** Use Django templates for email HTML

**Example:**
```python
from django.template.loader import render_to_string

html_content = render_to_string('emails/forensic_alert.html', context={
    'case_id': case_id,
    'risk_score': risk_score,
    ...
})
```

---

## ✅ What's Already Good

1. **Excellent retry logic** - Exponential backoff for timeouts and rate limits
2. **ThreadPoolExecutor** - Prevents thread explosion (better than raw threading)
3. **Graceful API unavailability handling** - App works without Brevo configured
4. **Professional email templates** - Good styling and information structure
5. **Async methods** - Non-blocking email sending
6. **Proper logging** - Comprehensive logging throughout
7. **Callback support** - Allows for result handling after async send
8. **SHA-256 chain hash displayed** - Good forensic integrity

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add missing `os` import | Low | 🔴 Crash |
| 2 | Add thread-safe singleton lock | Low | 🟠 Crash |
| 3 | Reduce ThreadPoolExecutor workers | Low | 🟠 Memory |
| 4 | Remove global instantiation | Low | 🟠 Init |
| 5 | Move time import to top | Low | 🟡 Perf |
| 6 | Delete empty views.py | Low | 🔵 Cleanup |
| 7 | Add service tests | Medium | 🔵 Quality |

---

## Files Connected (Dependencies)

- **intake/services.py** - Calls `brevo_dispatcher.send_forensic_alert()`
- **intake/views.py** - May trigger dispatch
- **cases/models.py** - IncidentReport linked via ForeignKey
- **directory/models.py** - AuthorityContact linked via ForeignKey
- **settings.py** - BREVO_API_KEY, BREVO_SENDER_EMAIL env vars

---

## Environment Variables Required

| Variable | Required | Default | Used For |
|----------|----------|---------|----------|
| `BREVO_API_KEY` | Yes | None | API authentication |
| `BREVO_SENDER_EMAIL` | No | `imara-alerts@projectimara.org` | Sender address |

---

## Code Metrics

- **Lines of Code:** 527
- **Methods:** 8
- **Classes:** 2 (BrevoDispatcher, BrevoDispatcherError)
- **HTML Lines (embedded):** ~240 (45% of file)
