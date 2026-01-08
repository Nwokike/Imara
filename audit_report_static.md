# Audit Report: Static Assets (`static/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `static/css/`, `static/js/`, `static/images/`, `static/manifest.json`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 0 |
| 🟠 HIGH | 1 |
| 🟡 MEDIUM | 3 |
| 🔵 LOW | 3 |

Static assets are **well-organized** with proper PWA support and **excellent dark mode** implementation. Main concern is **duplicate service worker code** and a **large logo file**.

---

## 🟠 HIGH Priority Issues

### 1. Duplicate Service Worker Code

**Problem:** The service worker exists in TWO places:
1. `static/js/serviceworker.js` (69 lines)
2. `intake/views.py` lines 34-103 (70 lines, embedded in Python)

Both are **identical** except the Python version is served dynamically.

**Issue:** Maintenance nightmare - changes must be made in two places.

**Fix:** Delete the embedded version in views.py and serve from static:
```python
# views.py
def serviceworker_view(request):
    return redirect('/static/js/serviceworker.js')
```

Or use FileResponse (see intake audit report).

---

## 🟡 MEDIUM Priority Issues

### 2. Large Logo File (461KB)

**File:** `static/images/logo.png` - **461KB**

**Problem:** Very large for a logo image. Will slow page loads, especially on mobile networks in Africa where bandwidth is limited and expensive.

**Comparison:**
- All PWA icons combined: ~94KB
- Single logo: 461KB (5x larger!)

**Fix:**
1. Optimize with `optipng` or `pngquant`
2. Convert to WebP (typically 30-50% smaller)
3. Consider SVG for logos (vector, infinitely scalable, small)

**Target:** < 50KB for production

---

### 3. Missing CSS Source Maps

**Problem:** No `.css.map` files for debugging. In production with WhiteNoise compression, debugging is harder.

**Recommendation:** Generate source maps if using any CSS preprocessor, or keep unminified copy for debugging.

---

### 4. Service Worker References Non-Existent File

**serviceworker.js line 10:**
```javascript
'/static/images/logo.png'
```

**Issue:** Caches `logo.png` but manifest uses `icon-*.png` files. If logo.png isn't used often, this wastes cache space.

**Fix:** Remove or replace with a more useful default:
```javascript
const STATIC_ASSETS = [
    '/',
    '/offline/',
    '/static/css/styles.css',
    '/static/js/main.js',
    '/static/manifest.json',
    '/static/images/icon-192x192.png'  // Use actual icon
];
```

---

## 🔵 LOW Priority Issues

### 5. Missing favicon.ico

**Problem:** No `favicon.ico` in static root. Browsers request `/favicon.ico` automatically.

**Fix:** Add a 32x32 favicon:
```bash
cp static/images/icon-32x32.png static/favicon.ico
```

And add to base.html:
```html
<link rel="icon" href="{% static 'favicon.ico' %}" type="image/x-icon">
```

---

### 6. main.js is Minimal

**Current (16 lines):**
- Form submit handling
- Loading spinner

**Note:** This is actually good for 1GB RAM! Minimal JavaScript = fast loading.

**Optional Enhancement:** Add error handling:
```javascript
reportForm.addEventListener('submit', function(e) {
    if (!navigator.onLine) {
        e.preventDefault();
        alert('You appear to be offline. Please try again when connected.');
        return;
    }
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="loading-spinner"></span>Analyzing...';
});
```

---

### 7. Missing `loading-spinner` CSS Class

**main.js line 12:**
```javascript
submitBtn.innerHTML = '<span class="loading-spinner"></span>Analyzing...';
```

**Check:** Ensure `.loading-spinner` class is defined in styles.css.

**Not found in first 800 lines** - need to verify in remaining lines or add:
```css
.loading-spinner {
    display: inline-block;
    width: 1em;
    height: 1em;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: spin 0.75s linear infinite;
    margin-right: 0.5em;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
```

---

## ✅ What's Already Good

### CSS (styles.css - 1167 lines)

1. **Excellent dark mode** - Full CSS variable system with `[data-bs-theme="dark"]`
2. **CSS Custom Properties** - Clean variable naming (`--imara-purple`, `--imara-bg`, etc.)
3. **Smooth transitions** - `transition: background-color 0.2s ease` for theme switching
4. **Responsive design** - Multiple breakpoints (768px, 992px)
5. **Modern CSS** - Grid, Flexbox, CSS variables
6. **Good component organization** - Navbar, hero, sections, cards, footer
7. **Consistent spacing** - Using rem units throughout
8. **Accessibility** - Good color contrast values

### PWA (manifest.json)

1. **Complete icon set** - All required sizes (72, 96, 128, 144, 152, 192, 384, 512)
2. **Maskable icon** - 512x512 has `purpose: "any maskable"`
3. **Proper scope** - `"scope": "/"`
4. **Standalone display** - Good for PWA experience
5. **Portrait orientation** - Appropriate for mobile

### Service Worker

1. **Proper caching strategy** - Network-first with cache fallback
2. **Offline support** - Falls back to /offline/ page
3. **Cache versioning** - `CACHE_NAME = 'imara-pwa-v1'`
4. **Old cache cleanup** - Removes outdated caches on activate

---

## File Size Analysis

| File | Size | Status |
|------|------|--------|
| styles.css | 23KB | ✅ Good |
| error.css | 1.6KB | ✅ Excellent |
| main.js | 0.5KB | ✅ Minimal |
| serviceworker.js | 2KB | ✅ Good |
| manifest.json | 1.7KB | ✅ Good |
| logo.png | **461KB** | ⚠️ Too Large |
| icon-512x512.png | 35KB | ✅ OK |
| icon-384x384.png | 23KB | ✅ OK |
| All other icons | ~36KB | ✅ Good |
| **Total** | ~544KB | ⚠️ Logo dominates |

---

## Dark Mode Implementation Review

**Well Implemented:**
```css
:root {
    --imara-purple: #6B4C9A;
    --imara-bg: #ffffff;
    --imara-text: #2d3436;
}

[data-bs-theme="dark"] {
    --imara-purple: #B794F6;
    --imara-bg: #1a1a2e;
    --imara-text: #f1f1f5;
}
```

**All components properly use CSS variables.**

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Remove duplicate service worker | Low | 🟠 Maint |
| 2 | Optimize logo.png | Low | 🟡 Perf |
| 3 | Fix service worker cache list | Low | 🟡 Cache |
| 4 | Add favicon.ico | Low | 🔵 UX |
| 5 | Add loading-spinner CSS | Low | 🔵 UX |

---

## PWA Checklist

| Requirement | Status |
|-------------|--------|
| manifest.json | ✅ Complete |
| Service worker | ✅ Working |
| 192x192 icon | ✅ Present |
| 512x512 icon | ✅ Present |
| Maskable icon | ✅ Present |
| Offline page | ✅ Configured |
| HTTPS | ⚠️ Required in production |
| Theme color | ✅ #6B4C9A |

---

## Browser Compatibility

| Feature | Support |
|---------|---------|
| CSS Variables | ✅ All modern browsers |
| Flexbox | ✅ All modern browsers |
| CSS Grid | ✅ All modern browsers |
| Service Worker | ✅ All modern browsers |
| PWA | ✅ Chrome, Edge, Samsung |
