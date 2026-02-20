"""
Shared safety and localization utilities for Project Imara.
Deduplicates logic between Telegram, Meta, and Web interfaces.
"""

SAFE_WORDS = ['IMARA STOP', 'STOP', 'CANCEL', 'HELP ME', 'EXIT', 'EMERGENCY']

def check_safe_word(text: str) -> bool:
    """Check if a message contains any of the predefined safe words."""
    if not text:
        return False
    text_upper = text.upper().strip()
    for safe_word in SAFE_WORDS:
        if safe_word in text_upper:
            return True
    return False

def get_localized_safety_message(language_preference: str = 'english') -> str:
    """Get a safety confirmation message in the user's preferred language."""
    lang = (language_preference or 'english').lower()
    
    if 'pidgin' in lang:
        return "🛡️ I don stop everything. You safe here.\n\nIf you dey danger, abeg call police or emergency number.\n\nType /start when you ready make we continue."
    elif 'swahili' in lang:
        return "🛡️ Nimesimamisha michakato yote. Uko salama hapa.\n\nIkiwa uko hatarini, tafadhali wasiliana na huduma za dharura.\n\nAndika /start utakapokuwa tayari kuendelea."
    
    return "🛡️ I've stopped all current processes. You're safe here.\n\nIf you're in immediate danger, please contact local emergency services.\n\nType /start when you're ready to continue."

def get_localized_location_prompt(language_preference: str = 'english') -> str:
    """Get a location request prompt in the user's preferred language."""
    lang = (language_preference or 'english').lower()
    
    if 'pidgin' in lang:
        return "⚠️ This one look like serious matter wey we fit report to police.\n\n📍 Abeg tell me which city and country you dey:\n\n(Example: Lagos, Nigeria)"
    elif 'swahili' in lang:
        return "⚠️ Hii inaonekana ni tishio kubwa ambalo linaweza kuripotiwa kwa mamlaka.\n\n📍 Tafadhali niambie uko katika jiji na nchi gani:\n\n(Mfano: Nairobi, Kenya)"
    
    return "⚠️ **Help Us Protect You**\n\nThe content you shared looks serious. 📍 **We need your location (City, Country)** to match you with the right support partner."

def sanitize_text(text: str) -> str:
    """Lightweight sanitization to strip common prompt injection patterns."""
    if not text:
        return ""
    
    injection_keywords = [
        "ignore previous instructions",
        "system prompt",
        "you are now",
        "acting as",
        "bypass",
        "forget everything",
    ]
    
    sanitized = text
    for keyword in injection_keywords:
        import re
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        sanitized = pattern.sub(f"[neutralized:{keyword}]", sanitized)
        
    return sanitized.strip()[:2000]
