# Audit Report: Imara Core App (`imara/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `imara/settings.py`, `imara/urls.py`, `imara/wsgi.py`, `imara/asgi.py`, `manage.py`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 2 |
| 🟠 HIGH | 4 |
| 🟡 MEDIUM | 5 |
| 🔵 LOW | 3 |

The core Django configuration has a solid security foundation but contains **critical deprecation issues** that will cause failures in Django 5.1+ and lacks **memory optimizations essential for the 1GB RAM constraint**.

---

## 🔴 CRITICAL Issues

### 1. Deprecated `STATICFILES_STORAGE` Setting (Line 116)

**Current Code:**
```python
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

**Problem:** `STATICFILES_STORAGE` was deprecated in Django 4.2 and **REMOVED in Django 5.1**. Since you're using Django 5.2.8, this code should already be throwing errors or silently failing.

**Fix Required:**
```python
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

---

### 2. Hardcoded Default SECRET_KEY (Line 11)

**Current Code:**
```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-dev-key-change-in-production')
```

**Problem:** If `SECRET_KEY` env var is missing in production, the app will run with a weak, known default key. This is a **severe security vulnerability**.

**Fix Required:**
```python
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
    else:
        raise ValueError("SECRET_KEY environment variable must be set in production")
```

---

## 🟠 HIGH Priority Issues

### 3. Missing `debug` Context Processor (Line 68-72)

**Current Code:**
```python
'context_processors': [
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
],
```

**Problem:** Missing `django.template.context_processors.debug` which is the Django default. This prevents `{{ debug }}` from working in templates.

**Fix:** Add the debug context processor:
```python
'context_processors': [
    'django.template.context_processors.debug',  # Add this
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
],
```

---

### 4. No Rate Limiting on Critical Endpoints

**Problem:** The Telegram webhook (`/webhook/telegram/`) and report form (`/report/`) have no rate limiting. This exposes the system to:
- DoS attacks
- Brute force abuse
- Excessive API costs (Groq/Gemini)

**Fix Required:** Add django-ratelimit or implement custom throttling:
```python
# Add to INSTALLED_APPS
'django_ratelimit',

# Add middleware in settings.py
MIDDLEWARE = [
    ...
    'django_ratelimit.middleware.RatelimitMiddleware',
]

RATELIMIT_VIEW = 'intake.views.ratelimited_error'
```

---

### 5. Missing Memory Optimization for 1GB RAM VM

**Problem:** No gunicorn configuration exists. With 1GB RAM:
- Default gunicorn workers will exhaust memory
- No worker recycling to prevent memory leaks
- No preload optimization

**Create `gunicorn.conf.py`:**
```python
import multiprocessing

workers = 2  # Low for 1GB RAM
threads = 2  # Use threads for I/O-bound work
worker_class = 'gthread'
max_requests = 500  # Recycle workers to prevent memory leaks
max_requests_jitter = 50
preload_app = True  # Reduce memory via copy-on-write
timeout = 120
graceful_timeout = 30
keepalive = 5

# Memory management
worker_tmp_dir = '/dev/shm'  # Use RAM for temp files (faster on Linux)
```

---

### 6. Database Connection Age May Cause Memory Issues (Line 86)

**Current Code:**
```python
conn_max_age=300,  # 5 minutes
```

**Problem:** Persistent connections hold memory. With 1GB RAM and low traffic, this could be reduced.

**Fix:** Consider reducing for low-memory environment:
```python
conn_max_age=60,  # 1 minute - better for low-memory
```

---

## 🟡 MEDIUM Priority Issues

### 7. No Session Backend Configuration

**Current:** Uses default database sessions (writes to PostgreSQL for every session).

**Problem:** Each request creates database queries for session management. This increases latency and database load.

**Recommendation:** For a low-traffic app, file-based or signed-cookie sessions are lighter:
```python
# For signed cookies (no database writes, but limited size)
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Alternative: File-based sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.file'
SESSION_FILE_PATH = '/tmp/django_sessions'
```

---

### 8. Missing `SECURE_REFERRER_POLICY` (Production Security)

**Problem:** No referrer policy is set. Modern browsers default to `strict-origin-when-cross-origin`, but it's best to be explicit.

**Fix:** Add to production security block:
```python
if not DEBUG:
    ...
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
```

---

### 9. No `CSRF_FAILURE_VIEW` Custom Handler

**Problem:** CSRF failures show a generic Django error page that may leak information or confuse users.

**Fix:** Add custom CSRF failure view:
```python
CSRF_FAILURE_VIEW = 'intake.views.csrf_failure'
```

---

### 10. Logging Configuration Issues

**Issues Found:**
1. No log rotation configured (logs could fill disk)
2. No structured logging (harder to parse)
3. DEBUG level logging in development could leak sensitive data

**Recommendation:** Consider adding file handler with rotation for production:
```python
'handlers': {
    'file': {
        'level': 'INFO',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': BASE_DIR / 'logs/imara.log',
        'maxBytes': 5 * 1024 * 1024,  # 5MB
        'backupCount': 3,
        'formatter': 'verbose',
    },
},
```

---

### 11. Hardcoded IP in ALLOWED_HOSTS (Line 26)

**Current Code:**
```python
'35.209.14.56',  # Hardcoded VM IP
```

**Problem:** Hardcoded IPs make infrastructure changes risky. If VM IP changes, the app breaks.

**Recommendation:** Use environment variable:
```python
if not DEBUG:
    ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        'imara.africa',
        'www.imara.africa',
    ]
    if os.environ.get('VM_IP'):
        ALLOWED_HOSTS.append(os.environ.get('VM_IP'))
```

---

## 🔵 LOW Priority Issues

### 12. pyproject.toml Has Wrong Project Name

**Current (pyproject.toml line 2):**
```toml
name = "repl-nix-workspace"
```

**Problem:** This is clearly a leftover from initial setup. Should be `imara` or `project-imara`.

---

### 13. No `DATA_UPLOAD_MAX_MEMORY_SIZE` Limit

**Problem:** Django defaults to 2.5MB for request body. With voice/image uploads, large files could exhaust memory.

**Fix:** Set explicit limits:
```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB before write to disk
```

---

### 14. `manage.py` Has Unnecessary Comments

**Current (manage.py lines 13-16):**
```python
raise ImportError(
    "Couldn't import Django. Are you sure it's installed and "
    "available on your PYTHONPATH environment variable? Did you "
    "forget to activate a virtual environment?"
) from exc
```

**Note:** This is Django's default boilerplate. Keep it—it's helpful for debugging.

---

## ✅ What's Already Good

1. **Security headers are properly configured** (HSTS, SSL redirect, secure cookies)
2. **WhiteNoise is correctly positioned** in middleware (right after SecurityMiddleware)
3. **Database connection health checks enabled** (`conn_health_checks=True`)
4. **SSL required for database** (`ssl_require=True`)
5. **Environment-based DEBUG** handling is correct
6. **Password validators** are complete
7. **CSRF trusted origins** properly configured

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Fix STATICFILES_STORAGE → STORAGES | Low | 🔴 Breaks |
| 2 | Fix SECRET_KEY fallback | Low | 🔴 Security |
| 3 | Add gunicorn.conf.py | Medium | 🟠 Memory |
| 4 | Add rate limiting | Medium | 🟠 Security |
| 5 | Add debug context processor | Low | 🟠 Templates |
| 6 | Session backend optimization | Low | 🟡 Perf |
| 7 | Add SECURE_REFERRER_POLICY | Low | 🟡 Security |
| 8 | Set upload size limits | Low | 🔵 Memory |

---

## Files Connected (Dependencies)

This core app connects to:
- **intake/urls.py** - Main URL routing
- **All apps in INSTALLED_APPS** - App configurations
- **templates/base.html** - Template directories
- **static/** - Static file directories
- **External Services**: Groq, Gemini, Brevo, Telegram (via env vars)

---

## Next Steps

1. Fix CRITICAL issues immediately (STORAGES migration, SECRET_KEY handling)
2. Create `gunicorn.conf.py` before production deployment
3. Add rate limiting to webhook and report endpoints
4. Run `python manage.py check --deploy` to verify production readiness
