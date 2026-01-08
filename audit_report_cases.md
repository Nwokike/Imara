# Audit Report: Cases App (`cases/`)

**Audit Date:** January 8, 2026  
**Auditor:** Comprehensive Production Audit  
**Scope:** `cases/models.py`, `cases/admin.py`, `cases/tests.py`, `cases/views.py`, `cases/apps.py`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 1 |
| 🟠 HIGH | 2 |
| 🟡 MEDIUM | 4 |
| 🔵 LOW | 2 |

The cases app handles **sensitive forensic evidence** for survivors. While the data model is well-designed, there are critical issues with hash generation logic and missing database optimizations.

---

## 🔴 CRITICAL Issues

### 1. Chain Hash Not Generated on First Save (Line 54-57)

**Current Code:**
```python
def save(self, *args, **kwargs):
    if not self.chain_hash and self.pk:
        self.generate_chain_hash()
    super().save(*args, **kwargs)
```

**Problem:** The condition `self.pk` is `None` on first save, so `generate_chain_hash()` is **never called on creation**. The hash is only generated on subsequent saves, but by then, `created_at` would already be set.

**Test Failure:** The test `test_chain_hash_generation` (line 19-22) expects hash to exist after creation:
```python
def test_chain_hash_generation(self):
    self.assertIsNotNone(self.report.chain_hash)  # This WILL FAIL
```

**Fix Required:**
```python
def save(self, *args, **kwargs):
    is_new = self.pk is None
    super().save(*args, **kwargs)  # Save first to get pk and created_at
    if is_new and not self.chain_hash:
        self.generate_chain_hash()
        super().save(update_fields=['chain_hash'])
```

---

## 🟠 HIGH Priority Issues

### 2. Missing Database Indexes

**Problem:** High-volume query fields lack indexes:
- `source` - filtered frequently in admin and queries
- `action` - filtered in dispatch logic
- `risk_score` - filtered for auto-dispatch (score > 7)
- `created_at` - ordered by this field
- `detected_location` - searched for authority matching

**Fix - Add indexes to model Meta:**
```python
class Meta:
    ordering = ['-created_at']
    indexes = [
        models.Index(fields=['source']),
        models.Index(fields=['action']),
        models.Index(fields=['risk_score']),
        models.Index(fields=['detected_location']),
        models.Index(fields=['-created_at']),  # For ordering
    ]
```

---

### 3. EvidenceAsset Hash Not Auto-Generated on Save

**Problem:** `generate_hash()` must be called manually after creating EvidenceAsset. The tests explicitly call it:
```python
evidence.generate_hash()
evidence.save()
```

This is error-prone and inconsistent with the intended forensic integrity.

**Fix - Override save:**
```python
def save(self, *args, **kwargs):
    if not self.sha256_digest:
        self.generate_hash()
    super().save(*args, **kwargs)
```

---

## 🟡 MEDIUM Priority Issues

### 4. Empty views.py File

**Current Code:**
```python
from django.shortcuts import render

# Create your views here.
```

**Problem:** Unused boilerplate code. Either remove the file or add views if needed.

**Options:**
1. **Delete file entirely** if no views are needed (app is data-only)
2. **Add useful views** like case detail API or evidence download

---

### 5. Potential Memory Issue with Large File Hashing (Line 82-87)

**Current Code:**
```python
def generate_hash(self):
    if self.file:
        file_hash = hashlib.sha256()
        for chunk in self.file.chunks():
            file_hash.update(chunk)
        self.sha256_digest = file_hash.hexdigest()
```

**Problem:** This is actually good chunked reading! But `self.file.chunks()` may fail if file is not open. Should handle edge cases:

**Improved Version:**
```python
def generate_hash(self):
    if self.file and hasattr(self.file, 'chunks'):
        try:
            file_hash = hashlib.sha256()
            self.file.seek(0)  # Reset file pointer
            for chunk in self.file.chunks():
                file_hash.update(chunk)
            self.sha256_digest = file_hash.hexdigest()
        except (IOError, ValueError):
            pass  # File not available
    elif self.derived_text:
        self.sha256_digest = hashlib.sha256(self.derived_text.encode()).hexdigest()
    return self.sha256_digest
```

---

### 6. Test Doesn't Verify Actual Hash on Creation

**Current Test (line 19-22):**
```python
def test_chain_hash_generation(self):
    self.assertIsNotNone(self.report.chain_hash)
    self.assertEqual(len(self.report.chain_hash), 64)
```

**Problems:**
1. Test will fail due to the save logic bug (Critical Issue #1)
2. Doesn't verify hash is deterministic
3. Doesn't test that modifying fields changes the hash

**Additional Test Needed:**
```python
def test_chain_hash_is_deterministic(self):
    """Same content should produce same hash"""
    hash1 = self.report.generate_chain_hash()
    hash2 = self.report.generate_chain_hash()
    self.assertEqual(hash1, hash2)

def test_chain_hash_changes_with_content(self):
    """Modified content should produce different hash"""
    original_hash = self.report.chain_hash
    self.report.original_text = "Modified content"
    new_hash = self.report.generate_chain_hash()
    self.assertNotEqual(original_hash, new_hash)
```

---

### 7. Missing Model Validation

**Problem:** No validation on models:
- `risk_score` can be any integer (should be 1-10)
- `reporter_email` should be validated if provided
- `detected_location` has no format validation

**Fix - Add validators:**
```python
from django.core.validators import MinValueValidator, MaxValueValidator

risk_score = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0), MaxValueValidator(10)]
)
```

---

## 🔵 LOW Priority Issues

### 8. Inconsistent Choice Naming

**Current:**
```python
SOURCE_CHOICES = [
    ('telegram', 'Telegram Bot'),
    ('web', 'Web Form'),
    ('whatsapp', 'WhatsApp'),
    ('instagram', 'Instagram'),
]
```

**Inconsistency:** `telegram` has "Bot" suffix, others don't. Consider:
```python
SOURCE_CHOICES = [
    ('telegram', 'Telegram'),
    ('web', 'Web'),
    ('whatsapp', 'WhatsApp'),
    ('instagram', 'Instagram'),
]
```

---

### 9. Admin Comment is Unnecessary

The admin.py is well-configured with proper fieldsets, filters, and readonly fields. No unnecessary comments found.

---

## ✅ What's Already Good

1. **UUID for case_id** - Prevents enumeration attacks
2. **SHA-256 hashing** - Forensically sound approach
3. **Proper ForeignKey cascade** - Evidence deleted with incident
4. **Good admin organization** - Fieldsets make UX clear
5. **DateTimeField auto fields** - Proper timestamp handling
6. **Chunked file reading** - Memory efficient for large files
7. **Related name on FK** - `evidence_assets` is clear

---

## Remediation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Fix chain hash save logic | Low | 🔴 Breaks |
| 2 | Add database indexes | Low | 🟠 Perf |
| 3 | Auto-generate evidence hash | Low | 🟠 Integrity |
| 4 | Add field validators | Low | 🟡 Data |
| 5 | Delete or use views.py | Low | 🟡 Cleanup |
| 6 | Expand test coverage | Medium | 🟡 Quality |

---

## Files Connected (Dependencies)

- **intake/services.py** - Creates IncidentReport instances
- **intake/views.py** - Creates EvidenceAsset for uploads
- **dispatch/service.py** - Reads risk_score for dispatch decisions
- **admin** - Displays and manages cases
- **templates/intake/result.html** - May display case_id

---

## Database Migration Check

**Current migrations:** Only `0001_initial.py` exists. After adding indexes, a new migration will be needed:
```bash
python manage.py makemigrations cases
```
