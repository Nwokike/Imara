"""
Location normalization and routing utilities for Project Imara.
Centralizes canonical African geography data for consistent partner matching.
"""
import logging
from .constants import AFRICAN_COUNTRIES, COUNTRY_SYNONYMS, CITY_TO_COUNTRY

logger = logging.getLogger(__name__)

def normalize_location(location_text: str) -> str:
    """
    Normalizes a raw location string (e.g., "Lagos, Nigeria" or "nairobi")
    to a canonical African country name.
    """
    if not location_text:
        return "Unknown"
        
    raw = location_text.strip().lower().replace("  ", " ")
    
    # 1. Try direct country match or synonym
    if "," in raw:
        candidate = raw.split(",")[-1].strip()
        candidate = COUNTRY_SYNONYMS.get(candidate, candidate)
        for c in AFRICAN_COUNTRIES:
            if c.lower() == candidate:
                return c
                
    # 2. Try city mapping
    for city, mapped_country in CITY_TO_COUNTRY.items():
        if city in raw:
            return mapped_country
            
    # 3. Try direct synonym match on full text
    candidate = COUNTRY_SYNONYMS.get(raw, raw).lower()
    for c in AFRICAN_COUNTRIES:
        if c.lower() == candidate:
            return c
            
    # 4. Substring detection
    for c in AFRICAN_COUNTRIES:
        if c.lower() in raw:
            return c
            
    return "Unknown"
