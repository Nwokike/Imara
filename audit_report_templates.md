# Audit Report: Templates (`templates/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `templates/base.html`, `templates/intake/`, `templates/400.html`, `templates/403.html`, `templates/404.html`, `templates/500.html`, `templates/offline.html`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 0 |
| 🟠 HIGH | 1 |
| 🟡 MEDIUM | 3 |
| 🔵 LOW | 2 |

Templates are **well-structured** with proper inheritance and good Bootstrap 5 usage. Main concern is **inline JavaScript** in base.html which should be externalized.

---

## 🟠 HIGH Priority Issues

### 1. Inline JavaScript in base.html (Lines 122-165)

**Current Code:**
```html
<script>
    (function () {
        const toggle = document.getElementById('themeToggle');
        const html = document.documentElement;
        // ... 20+ lines of theme toggle code
    })();

    if ('serviceWorker' in navigator) {
        // ... service worker registration
    }

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        // ... smooth scroll code
    });
</script>
```

**Problems:**
1. ~45 lines of inline JavaScript violates CSP best practices
2. Cannot be cached separately by browsers
3. Harder to maintain and debug
4. Blocks rendering

**Fix - Move to external file:**
```javascript
// static/js/theme.js
document.addEventListener('DOMContentLoaded', function() {
    initThemeToggle();
    registerServiceWorker();
    initSmoothScroll();
});
```

And in base.html:
```html
<script src="{% static 'js/theme.js' %}"></script>
```

---

## 🟡 MEDIUM Priority Issues

### 2. Cache-Control Meta Tags Prevent Caching (base.html lines 16-18)

**Current Code:**
```html
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
```

**Problem:** These meta tags disable ALL browser caching, which:
- Increases server load
- Slows page loads (especially on mobile networks)
- Conflicts with PWA caching strategy

**Recommendation:** Remove these meta tags and rely on proper HTTP headers set by Django/WhiteNoise for caching.

---

### 3. Error Pages Don't Extend base.html

**Files:** `400.html`, `403.html`, `404.html`, `500.html`, `offline.html`

**Current:** Each error page is standalone with duplicate head elements.

**Example (404.html):**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <!-- Duplicate meta tags, fonts, icons -->
</head>
```

**Problem:**
- Maintenance burden (changes needed in 5 files)
- No dark mode support (unlike main site)
- No consistent branding

**Fix:** Create error base template:
```html
<!-- templates/error_base.html -->
{% load static %}
<!DOCTYPE html>
<html lang="en" data-bs-theme="light">
<head>
    <!-- Common head elements -->
</head>
<body>
    {% block error_content %}{% endblock %}
</body>
</html>
```

---

### 4. user-scalable=no is Accessibility Concern (base.html line 7)

**Current Code:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
```

**Problem:** `user-scalable=no` prevents users from zooming, which is an accessibility issue for visually impaired users.

**Fix:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

---

## 🔵 LOW Priority Issues

### 5. Hardcoded Telegram Bot URL

**Multiple files reference:**
```html
<a href="https://t.me/project_imara_bot" target="_blank">
```

**Recommendation:** Make this a Django setting or context variable:
```python
# settings.py
TELEGRAM_BOT_URL = "https://t.me/project_imara_bot"
```

---

### 6. Form Error Display Could Be More Accessible

**report_form.html lines 25-37:**
```html
{% if form.errors %}
<div class="alert alert-danger">
    {% for field in form %}
        {% for error in field.errors %}
            {{ error }}<br>
        {% endfor %}
    {% endfor %}
</div>
{% endif %}
```

**Enhancement:** Add `role="alert"` and `aria-live="polite"` for screen readers (already has `role="alert"` - good!).

---

## ✅ What's Already Good

1. **Proper template inheritance** - All pages extend base.html
2. **Bootstrap 5.3** - Modern, well-maintained framework
3. **Google Fonts preconnect** - Performance optimization
4. **PWA meta tags** - Complete set for mobile apps
5. **CSRF protection** - `{% csrf_token %}` in forms
6. **Semantic HTML** - Proper use of `<section>`, `<main>`, `<nav>`, `<footer>`
7. **Accessibility** - ARIA labels on toggle button
8. **Responsive design** - Proper viewport and mobile classes
9. **Error handling** - Custom error pages for 400, 403, 404, 500
10. **Offline page** - PWA fallback page

---

## Template Inventory

| Template | Lines | Purpose |
|----------|-------|---------|
| base.html | 168 | Master template with nav/footer |
| intake/index.html | 496 | Landing page |
| intake/report_form.html | 119 | Report submission form |
| intake/result.html | 174 | Analysis results |
| offline.html | 24 | PWA offline fallback |
| 400.html | 24 | Bad Request error |
| 403.html | 25 | Forbidden error |
| 404.html | 25 | Not Found error |
| 500.html | 24 | Server Error |
| **Total** | **1,079** | |

---

## CDN Dependencies

| Resource | Version | Purpose |
|----------|---------|---------|
| Bootstrap CSS | 5.3.2 | UI framework |
| Bootstrap JS | 5.3.2 | Interactivity |
| Bootstrap Icons | 1.11.1 | Icon font |
| Inter Font | - | Typography |

**Risk:** CDN outage could break the site.

**Recommendation:** Consider self-hosting critical assets or adding fallbacks.

---

## SEO Analysis

| Element | Status |
|---------|--------|
| Title tag | ✅ Unique per page |
| Meta description | ✅ Present in base |
| H1 heading | ✅ Single per page |
| Semantic HTML | ✅ Good |
| Alt text on images | ✅ Present |
| Open Graph tags | ⚠️ Missing |
| Twitter cards | ⚠️ Missing |

**Fix - Add OG tags:**
```html
<meta property="og:title" content="Project Imara - Digital Bodyguard">
<meta property="og:description" content="...">
<meta property="og:image" content="{% static 'images/icon-512x512.png' %}">
<meta property="og:type" content="website">
```

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Externalize inline JavaScript | Medium | 🟠 CSP |
| 2 | Remove cache-control meta | Low | 🟡 Perf |
| 3 | Fix user-scalable=no | Low | 🟡 A11y |
| 4 | Unify error page templates | Low | 🟡 Maint |
| 5 | Add OG/Twitter meta tags | Low | 🔵 SEO |
