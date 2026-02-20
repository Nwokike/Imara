"""
Canonical partner/location constants.

We keep a single canonical list of African countries to:
- power the partner inquiry dropdown
- normalize AI-detected locations to partner jurisdictions
"""

# Ordered (region, [countries...]) for stable UI rendering.
AFRICAN_COUNTRIES_BY_REGION: list[tuple[str, list[str]]] = [
    ("North Africa", [
        "Algeria",
        "Egypt",
        "Libya",
        "Morocco",
        "Sudan",
        "Tunisia",
    ]),
    ("West Africa", [
        "Benin",
        "Burkina Faso",
        "Cape Verde",
        "Côte d’Ivoire",
        "Gambia",
        "Ghana",
        "Guinea",
        "Guinea-Bissau",
        "Liberia",
        "Mali",
        "Mauritania",
        "Niger",
        "Nigeria",
        "Senegal",
        "Sierra Leone",
        "Togo",
    ]),
    ("Central Africa", [
        "Cameroon",
        "Central African Republic",
        "Chad",
        "Republic of the Congo",
        "Democratic Republic of the Congo",
        "Equatorial Guinea",
        "Gabon",
        "São Tomé and Príncipe",
    ]),
    ("East Africa", [
        "Burundi",
        "Comoros",
        "Djibouti",
        "Eritrea",
        "Ethiopia",
        "Kenya",
        "Madagascar",
        "Malawi",
        "Mauritius",
        "Mozambique",
        "Rwanda",
        "Seychelles",
        "Somalia",
        "South Sudan",
        "Tanzania",
        "Uganda",
        "Zambia",
        "Zimbabwe",
    ]),
    ("Southern Africa", [
        "Angola",
        "Botswana",
        "Eswatini",
        "Lesotho",
        "Namibia",
        "South Africa",
    ]),
]


AFRICAN_COUNTRIES: list[str] = [c for _, countries in AFRICAN_COUNTRIES_BY_REGION for c in countries]

# Common synonyms/abbreviations -> canonical country
COUNTRY_SYNONYMS: dict[str, str] = {
    "naija": "Nigeria",
    "drc": "Democratic Republic of the Congo",
    "dr congo": "Democratic Republic of the Congo",
    "democratic republic of congo": "Democratic Republic of the Congo",
    "congo-kinshasa": "Democratic Republic of the Congo",
    "congo brazzaville": "Republic of the Congo",
    "republic of congo": "Republic of the Congo",
    "ivory coast": "Côte d’Ivoire",
    "cote d'ivoire": "Côte d’Ivoire",
    "cote d’ivoire": "Côte d’Ivoire",
    "swaziland": "Eswatini",
    "cabo verde": "Cape Verde",
    "sao tome and principe": "São Tomé and Príncipe",
    "são tomé and príncipe": "São Tomé and Príncipe",
    "sao tome & principe": "São Tomé and Príncipe",
}

# Mapping common cities to countries
CITY_TO_COUNTRY: dict[str, str] = {
    # Nigeria
    "lagos": "Nigeria",
    "abuja": "Nigeria",
    "port harcourt": "Nigeria",
    "ibadan": "Nigeria",
    "kano": "Nigeria",
    "enugu": "Nigeria",
    "benin city": "Nigeria",
    "kaduna": "Nigeria",
    "jos": "Nigeria",
    "ilaro": "Nigeria",
    
    # Ghana
    "accra": "Ghana",
    "kumasi": "Ghana",
    "tamale": "Ghana",
    "takoradi": "Ghana",
    
    # Kenya
    "nairobi": "Kenya",
    "mombasa": "Kenya",
    "kisumu": "Kenya",
    "nakuru": "Kenya",
    
    # South Africa
    "johannesburg": "South Africa",
    "cape town": "South Africa",
    "durban": "South Africa",
    "pretoria": "South Africa",
}

