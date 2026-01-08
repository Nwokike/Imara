# Audit Report: Directory App (`directory/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `directory/models.py`, `directory/admin.py`, `directory/tests.py`, `directory/views.py`, `directory/management/commands/seed_authorities.py`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 0 |
| 🟠 HIGH | 2 |
| 🟡 MEDIUM | 3 |
| 🔵 LOW | 2 |

This app is well-designed and tested. Main concerns are **query efficiency** and **missing database indexes** for a location-based search system.

---

## 🟠 HIGH Priority Issues

### 1. Redundant Database Queries in `find_by_location` (Lines 42-55)

**Current Code:**
```python
@classmethod
def find_by_location(cls, location):
    if not location:
        return cls.objects.filter(is_active=True).order_by('-priority').first()
    
    location_lower = location.lower()
    contacts = cls.objects.filter(
        is_active=True,
        jurisdiction_name__icontains=location_lower
    ).order_by('-priority')
    
    if contacts.exists():  # <- First query
        return contacts.first()  # <- Second query (redundant!)
    
    return cls.objects.filter(is_active=True).order_by('-priority').first()
```

**Problems:**
1. `.exists()` and `.first()` are **two separate queries** when one would suffice
2. The fallback path executes **yet another query**

**Fix - Single optimized query:**
```python
@classmethod
def find_by_location(cls, location):
    if not location:
        return cls.objects.filter(is_active=True).order_by('-priority').first()
    
    location_lower = location.lower()
    contact = cls.objects.filter(
        is_active=True,
        jurisdiction_name__icontains=location_lower
    ).order_by('-priority').first()  # Single query
    
    if contact:
        return contact
    
    return cls.objects.filter(is_active=True).order_by('-priority').first()
```

---

### 2. Missing Database Indexes

**Problem:** The model is searched by `jurisdiction_name` and filtered by `is_active`, but has no indexes.

**Current Meta (lines 33-36):**
```python
class Meta:
    ordering = ['-priority', 'jurisdiction_name']
    verbose_name = 'Authority Contact'
    verbose_name_plural = 'Authority Contacts'
```

**Fix - Add indexes:**
```python
class Meta:
    ordering = ['-priority', 'jurisdiction_name']
    verbose_name = 'Authority Contact'
    verbose_name_plural = 'Authority Contacts'
    indexes = [
        models.Index(fields=['is_active', 'jurisdiction_name']),
        models.Index(fields=['is_active', '-priority']),
    ]
```

---

## 🟡 MEDIUM Priority Issues

### 3. No Validation on Priority Field (Line 26)

**Current Code:**
```python
priority = models.IntegerField(default=1, help_text="Higher priority contacts are preferred (1-10)")
```

**Problem:** Help text says 1-10, but no validation enforces this.

**Fix:**
```python
from django.core.validators import MinValueValidator, MaxValueValidator

priority = models.IntegerField(
    default=1,
    validators=[MinValueValidator(1), MaxValueValidator(10)],
    help_text="Higher priority contacts are preferred (1-10)"
)
```

---

### 4. Empty views.py File

**Current Code:**
```python
from django.shortcuts import render

# Create your views here.
```

**Action:** Delete file entirely—this is a data-only app with no views needed.

---

### 5. Seed Command Could Use Bulk Operations

**Current (lines 215-226):**
```python
for auth_data in authorities:
    authority, created = AuthorityContact.objects.update_or_create(...)
```

**Problem:** With 20 entries, this creates 20+ database queries. For the current small dataset this is fine, but for future scalability consider bulk operations.

**Note:** `update_or_create` is appropriate here for idempotency. Keep as-is for now but document the trade-off.

---

## 🔵 LOW Priority Issues

### 6. Missing Email Validation in Seed Data

Some seed data emails may not be verified:
- Line 202: `alerts@pawsn.org` - Is this a real email?
- Line 162: `dovvsu@police.gov.gh` - Government emails may change

**Recommendation:** Add a `verified` boolean field or `last_verified_at` timestamp.

---

### 7. Test Could Be More Robust

**Current test (line 36-40):**
```python
def test_fallback_logic(self):
    """Test that it returns a default if location is unknown"""
    authority = AuthorityContact.find_by_location("Mars")
    self.assertIsNotNone(authority)
```

**Improvement:** Test should verify the *correct* fallback is returned (highest priority):
```python
def test_fallback_logic(self):
    """Test that it returns highest priority contact for unknown location"""
    authority = AuthorityContact.find_by_location("Mars")
    self.assertIsNotNone(authority)
    # Should return Lagos or Kenya DCI (both priority 10)
    self.assertEqual(authority.priority, 10)
```

---

## ✅ What's Already Good

1. **Excellent seed data** - 20 real African helplines with accurate info
2. **Idempotent seeding** - `update_or_create` allows re-running safely
3. **Good admin configuration** - Editable fields, proper fieldsets
4. **Well-structured tags** - JSONField allows flexible categorization
5. **Case-insensitive search** - `icontains` handles user input variations
6. **Priority-based ordering** - Higher priority contacts first
7. **is_active flag** - Allows soft disabling without deletion

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Fix redundant queries in find_by_location | Low | 🟠 Perf |
| 2 | Add database indexes | Low | 🟠 Perf |
| 3 | Add priority field validators | Low | 🟡 Data |
| 4 | Delete empty views.py | Low | 🔵 Cleanup |

---

## Files Connected (Dependencies)

- **dispatch/service.py** - Calls `AuthorityContact.find_by_location()`
- **intake/services.py** - May call find_by_location for auto-dispatch
- **admin** - Manages authority contacts

---

## Data Quality Notes

The seed data includes helplines for:
- **Kenya** (3 contacts): FIDA, Befrienders, Childline
- **Uganda** (3 contacts): Mifumi, Mental Health, Sauti
- **Tanzania** (3 contacts): WLAC, Mental Health Trust, C-Sema
- **South Africa** (3 contacts): SADAG, GBV Command Centre, Substance Line
- **Nigeria** (3 contacts): MANI, DSVRT, Women Safe House
- **Ghana** (3 contacts): DOVVSU, Mental Health Lifeline, Stop Abuse
- **Rwanda** (1 contact): Child Helpline
- **Africa Regional** (1 contact): Pan-African fallback

**Total: 20 pre-seeded authorities** - Matches README claim of "19+ verified helplines"
