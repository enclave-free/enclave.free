"""
Static ISO 3166-1 alpha-2 country codes mapped to UN M49 region/subregion groupings.

This is the lookup that makes resource coverage hierarchical: a resource declares a
coverage *scope* (one country / a subregion / a region / global) while a user query is a
single country. Matching is containment — does a resource's scope contain the user's
country? — and ranking prefers specificity (country > subregion > region > global).

The data ships as plain module constants (matching the SUPPORTED_DEFAULT_LANGUAGES
convention in models.py) and is seeded into the country_regions table at startup so it can
be JOINed in SQL. No external/runtime dependency.

M49 region codes (continental):
  002 Africa | 019 Americas | 142 Asia | 150 Europe | 009 Oceania
"""

from __future__ import annotations

import unicodedata
from typing import Iterator, Optional, TypedDict


REGION_NAMES: dict[str, str] = {
    "002": "Africa",
    "019": "Americas",
    "142": "Asia",
    "150": "Europe",
    "009": "Oceania",
}

SUBREGION_NAMES: dict[str, str] = {
    # Africa
    "015": "Northern Africa",
    "011": "Western Africa",
    "017": "Middle Africa",
    "014": "Eastern Africa",
    "018": "Southern Africa",
    # Americas
    "021": "Northern America",
    "013": "Central America",
    "005": "South America",
    "029": "Caribbean",
    # Asia
    "143": "Central Asia",
    "030": "Eastern Asia",
    "035": "South-eastern Asia",
    "034": "Southern Asia",
    "145": "Western Asia",
    # Europe
    "154": "Northern Europe",
    "155": "Western Europe",
    "151": "Eastern Europe",
    "039": "Southern Europe",
    # Oceania
    "053": "Australia and New Zealand",
    "054": "Melanesia",
    "057": "Micronesia",
    "061": "Polynesia",
}

# Every code used by SUBREGION_NAMES maps up to a continental region.
_SUBREGION_TO_REGION: dict[str, str] = {
    "015": "002", "011": "002", "017": "002", "014": "002", "018": "002",
    "021": "019", "013": "019", "005": "019", "029": "019",
    "143": "142", "030": "142", "035": "142", "034": "142", "145": "142",
    "154": "150", "155": "150", "151": "150", "039": "150",
    "053": "009", "054": "009", "057": "009", "061": "009",
}


class CountryEntry(TypedDict):
    name: str
    subregion: str  # M49 subregion code


# ISO 3166-1 alpha-2 -> {canonical English name, M49 subregion}.
# Region is derived from the subregion via _SUBREGION_TO_REGION.
COUNTRIES: dict[str, CountryEntry] = {
    # --- Central America (013) ---
    "BZ": {"name": "Belize", "subregion": "013"},
    "CR": {"name": "Costa Rica", "subregion": "013"},
    "GT": {"name": "Guatemala", "subregion": "013"},
    "HN": {"name": "Honduras", "subregion": "013"},
    "MX": {"name": "Mexico", "subregion": "013"},
    "NI": {"name": "Nicaragua", "subregion": "013"},
    "PA": {"name": "Panama", "subregion": "013"},
    "SV": {"name": "El Salvador", "subregion": "013"},
    # --- South America (005) ---
    "AR": {"name": "Argentina", "subregion": "005"},
    "BO": {"name": "Bolivia", "subregion": "005"},
    "BR": {"name": "Brazil", "subregion": "005"},
    "CL": {"name": "Chile", "subregion": "005"},
    "CO": {"name": "Colombia", "subregion": "005"},
    "EC": {"name": "Ecuador", "subregion": "005"},
    "GY": {"name": "Guyana", "subregion": "005"},
    "PE": {"name": "Peru", "subregion": "005"},
    "PY": {"name": "Paraguay", "subregion": "005"},
    "SR": {"name": "Suriname", "subregion": "005"},
    "UY": {"name": "Uruguay", "subregion": "005"},
    "VE": {"name": "Venezuela", "subregion": "005"},
    # --- Northern America (021) ---
    "CA": {"name": "Canada", "subregion": "021"},
    "US": {"name": "United States", "subregion": "021"},
    # --- Caribbean (029) ---
    "AG": {"name": "Antigua and Barbuda", "subregion": "029"},
    "BS": {"name": "Bahamas", "subregion": "029"},
    "BB": {"name": "Barbados", "subregion": "029"},
    "CU": {"name": "Cuba", "subregion": "029"},
    "DM": {"name": "Dominica", "subregion": "029"},
    "DO": {"name": "Dominican Republic", "subregion": "029"},
    "GD": {"name": "Grenada", "subregion": "029"},
    "HT": {"name": "Haiti", "subregion": "029"},
    "JM": {"name": "Jamaica", "subregion": "029"},
    "KN": {"name": "Saint Kitts and Nevis", "subregion": "029"},
    "LC": {"name": "Saint Lucia", "subregion": "029"},
    "VC": {"name": "Saint Vincent and the Grenadines", "subregion": "029"},
    "TT": {"name": "Trinidad and Tobago", "subregion": "029"},
    # --- Northern Africa (015) ---
    "DZ": {"name": "Algeria", "subregion": "015"},
    "EG": {"name": "Egypt", "subregion": "015"},
    "LY": {"name": "Libya", "subregion": "015"},
    "MA": {"name": "Morocco", "subregion": "015"},
    "SD": {"name": "Sudan", "subregion": "015"},
    "TN": {"name": "Tunisia", "subregion": "015"},
    "EH": {"name": "Western Sahara", "subregion": "015"},
    # --- Western Africa (011) ---
    "BJ": {"name": "Benin", "subregion": "011"},
    "BF": {"name": "Burkina Faso", "subregion": "011"},
    "CV": {"name": "Cabo Verde", "subregion": "011"},
    "CI": {"name": "Côte d'Ivoire", "subregion": "011"},
    "GM": {"name": "Gambia", "subregion": "011"},
    "GH": {"name": "Ghana", "subregion": "011"},
    "GN": {"name": "Guinea", "subregion": "011"},
    "GW": {"name": "Guinea-Bissau", "subregion": "011"},
    "LR": {"name": "Liberia", "subregion": "011"},
    "ML": {"name": "Mali", "subregion": "011"},
    "MR": {"name": "Mauritania", "subregion": "011"},
    "NE": {"name": "Niger", "subregion": "011"},
    "NG": {"name": "Nigeria", "subregion": "011"},
    "SN": {"name": "Senegal", "subregion": "011"},
    "SL": {"name": "Sierra Leone", "subregion": "011"},
    "TG": {"name": "Togo", "subregion": "011"},
    # --- Middle Africa (017) ---
    "AO": {"name": "Angola", "subregion": "017"},
    "CM": {"name": "Cameroon", "subregion": "017"},
    "CF": {"name": "Central African Republic", "subregion": "017"},
    "TD": {"name": "Chad", "subregion": "017"},
    "CG": {"name": "Republic of the Congo", "subregion": "017"},
    "CD": {"name": "Democratic Republic of the Congo", "subregion": "017"},
    "GQ": {"name": "Equatorial Guinea", "subregion": "017"},
    "GA": {"name": "Gabon", "subregion": "017"},
    "ST": {"name": "São Tomé and Príncipe", "subregion": "017"},
    # --- Eastern Africa (014) ---
    "BI": {"name": "Burundi", "subregion": "014"},
    "KM": {"name": "Comoros", "subregion": "014"},
    "DJ": {"name": "Djibouti", "subregion": "014"},
    "ER": {"name": "Eritrea", "subregion": "014"},
    "ET": {"name": "Ethiopia", "subregion": "014"},
    "KE": {"name": "Kenya", "subregion": "014"},
    "MG": {"name": "Madagascar", "subregion": "014"},
    "MW": {"name": "Malawi", "subregion": "014"},
    "MU": {"name": "Mauritius", "subregion": "014"},
    "MZ": {"name": "Mozambique", "subregion": "014"},
    "RW": {"name": "Rwanda", "subregion": "014"},
    "SC": {"name": "Seychelles", "subregion": "014"},
    "SO": {"name": "Somalia", "subregion": "014"},
    "SS": {"name": "South Sudan", "subregion": "014"},
    "TZ": {"name": "Tanzania", "subregion": "014"},
    "UG": {"name": "Uganda", "subregion": "014"},
    "ZM": {"name": "Zambia", "subregion": "014"},
    "ZW": {"name": "Zimbabwe", "subregion": "014"},
    # --- Southern Africa (018) ---
    "BW": {"name": "Botswana", "subregion": "018"},
    "SZ": {"name": "Eswatini", "subregion": "018"},
    "LS": {"name": "Lesotho", "subregion": "018"},
    "NA": {"name": "Namibia", "subregion": "018"},
    "ZA": {"name": "South Africa", "subregion": "018"},
    # --- Western Asia (145) ---
    "AM": {"name": "Armenia", "subregion": "145"},
    "AZ": {"name": "Azerbaijan", "subregion": "145"},
    "BH": {"name": "Bahrain", "subregion": "145"},
    "CY": {"name": "Cyprus", "subregion": "145"},
    "GE": {"name": "Georgia", "subregion": "145"},
    "IQ": {"name": "Iraq", "subregion": "145"},
    "IL": {"name": "Israel", "subregion": "145"},
    "JO": {"name": "Jordan", "subregion": "145"},
    "KW": {"name": "Kuwait", "subregion": "145"},
    "LB": {"name": "Lebanon", "subregion": "145"},
    "OM": {"name": "Oman", "subregion": "145"},
    "PS": {"name": "Palestine", "subregion": "145"},
    "QA": {"name": "Qatar", "subregion": "145"},
    "SA": {"name": "Saudi Arabia", "subregion": "145"},
    "SY": {"name": "Syria", "subregion": "145"},
    "TR": {"name": "Turkey", "subregion": "145"},
    "AE": {"name": "United Arab Emirates", "subregion": "145"},
    "YE": {"name": "Yemen", "subregion": "145"},
    # --- Central Asia (143) ---
    "KZ": {"name": "Kazakhstan", "subregion": "143"},
    "KG": {"name": "Kyrgyzstan", "subregion": "143"},
    "TJ": {"name": "Tajikistan", "subregion": "143"},
    "TM": {"name": "Turkmenistan", "subregion": "143"},
    "UZ": {"name": "Uzbekistan", "subregion": "143"},
    # --- Southern Asia (034) ---
    "AF": {"name": "Afghanistan", "subregion": "034"},
    "BD": {"name": "Bangladesh", "subregion": "034"},
    "BT": {"name": "Bhutan", "subregion": "034"},
    "IN": {"name": "India", "subregion": "034"},
    "IR": {"name": "Iran", "subregion": "034"},
    "MV": {"name": "Maldives", "subregion": "034"},
    "NP": {"name": "Nepal", "subregion": "034"},
    "PK": {"name": "Pakistan", "subregion": "034"},
    "LK": {"name": "Sri Lanka", "subregion": "034"},
    # --- Eastern Asia (030) ---
    "CN": {"name": "China", "subregion": "030"},
    "JP": {"name": "Japan", "subregion": "030"},
    "KP": {"name": "North Korea", "subregion": "030"},
    "KR": {"name": "South Korea", "subregion": "030"},
    "MN": {"name": "Mongolia", "subregion": "030"},
    "TW": {"name": "Taiwan", "subregion": "030"},
    # --- South-eastern Asia (035) ---
    "BN": {"name": "Brunei", "subregion": "035"},
    "KH": {"name": "Cambodia", "subregion": "035"},
    "ID": {"name": "Indonesia", "subregion": "035"},
    "LA": {"name": "Laos", "subregion": "035"},
    "MY": {"name": "Malaysia", "subregion": "035"},
    "MM": {"name": "Myanmar", "subregion": "035"},
    "PH": {"name": "Philippines", "subregion": "035"},
    "SG": {"name": "Singapore", "subregion": "035"},
    "TH": {"name": "Thailand", "subregion": "035"},
    "TL": {"name": "Timor-Leste", "subregion": "035"},
    "VN": {"name": "Vietnam", "subregion": "035"},
    # --- Northern Europe (154) ---
    "DK": {"name": "Denmark", "subregion": "154"},
    "EE": {"name": "Estonia", "subregion": "154"},
    "FI": {"name": "Finland", "subregion": "154"},
    "IS": {"name": "Iceland", "subregion": "154"},
    "IE": {"name": "Ireland", "subregion": "154"},
    "LV": {"name": "Latvia", "subregion": "154"},
    "LT": {"name": "Lithuania", "subregion": "154"},
    "NO": {"name": "Norway", "subregion": "154"},
    "SE": {"name": "Sweden", "subregion": "154"},
    "GB": {"name": "United Kingdom", "subregion": "154"},
    # --- Western Europe (155) ---
    "AT": {"name": "Austria", "subregion": "155"},
    "BE": {"name": "Belgium", "subregion": "155"},
    "FR": {"name": "France", "subregion": "155"},
    "DE": {"name": "Germany", "subregion": "155"},
    "LI": {"name": "Liechtenstein", "subregion": "155"},
    "LU": {"name": "Luxembourg", "subregion": "155"},
    "MC": {"name": "Monaco", "subregion": "155"},
    "NL": {"name": "Netherlands", "subregion": "155"},
    "CH": {"name": "Switzerland", "subregion": "155"},
    # --- Eastern Europe (151) ---
    "BY": {"name": "Belarus", "subregion": "151"},
    "BG": {"name": "Bulgaria", "subregion": "151"},
    "CZ": {"name": "Czechia", "subregion": "151"},
    "HU": {"name": "Hungary", "subregion": "151"},
    "PL": {"name": "Poland", "subregion": "151"},
    "MD": {"name": "Moldova", "subregion": "151"},
    "RO": {"name": "Romania", "subregion": "151"},
    "RU": {"name": "Russia", "subregion": "151"},
    "SK": {"name": "Slovakia", "subregion": "151"},
    "UA": {"name": "Ukraine", "subregion": "151"},
    # --- Southern Europe (039) ---
    "AL": {"name": "Albania", "subregion": "039"},
    "AD": {"name": "Andorra", "subregion": "039"},
    "BA": {"name": "Bosnia and Herzegovina", "subregion": "039"},
    "HR": {"name": "Croatia", "subregion": "039"},
    "GR": {"name": "Greece", "subregion": "039"},
    "IT": {"name": "Italy", "subregion": "039"},
    "MT": {"name": "Malta", "subregion": "039"},
    "ME": {"name": "Montenegro", "subregion": "039"},
    "MK": {"name": "North Macedonia", "subregion": "039"},
    "PT": {"name": "Portugal", "subregion": "039"},
    "SM": {"name": "San Marino", "subregion": "039"},
    "RS": {"name": "Serbia", "subregion": "039"},
    "SI": {"name": "Slovenia", "subregion": "039"},
    "ES": {"name": "Spain", "subregion": "039"},
    "VA": {"name": "Vatican City", "subregion": "039"},
    # --- Australia and New Zealand (053) ---
    "AU": {"name": "Australia", "subregion": "053"},
    "NZ": {"name": "New Zealand", "subregion": "053"},
    # --- Melanesia (054) ---
    "FJ": {"name": "Fiji", "subregion": "054"},
    "PG": {"name": "Papua New Guinea", "subregion": "054"},
    "SB": {"name": "Solomon Islands", "subregion": "054"},
    "VU": {"name": "Vanuatu", "subregion": "054"},
    # --- Micronesia (057) ---
    "FM": {"name": "Micronesia", "subregion": "057"},
    "KI": {"name": "Kiribati", "subregion": "057"},
    "MH": {"name": "Marshall Islands", "subregion": "057"},
    "NR": {"name": "Nauru", "subregion": "057"},
    "PW": {"name": "Palau", "subregion": "057"},
    # --- Polynesia (061) ---
    "WS": {"name": "Samoa", "subregion": "061"},
    "TO": {"name": "Tonga", "subregion": "061"},
    "TV": {"name": "Tuvalu", "subregion": "061"},
}

# Common name variants / colloquial forms -> ISO alpha-2. Keys are lowercased.
ALIASES: dict[str, str] = {
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "united states of america": "US",
    "america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "great britain": "GB",
    "britain": "GB",
    "england": "GB",
    "south korea": "KR",
    "republic of korea": "KR",
    "north korea": "KP",
    "dprk": "KP",
    "drc": "CD",
    "dr congo": "CD",
    "democratic republic of congo": "CD",
    "congo-kinshasa": "CD",
    "congo-brazzaville": "CG",
    "ivory coast": "CI",
    "cote d'ivoire": "CI",
    "cape verde": "CV",
    "swaziland": "SZ",
    "burma": "MM",
    "east timor": "TL",
    "vatican": "VA",
    "holy see": "VA",
    "palestinian territories": "PS",
    "syrian arab republic": "SY",
    "russian federation": "RU",
    "iran (islamic republic of)": "IR",
    "bolivia (plurinational state of)": "BO",
    "venezuela (bolivarian republic of)": "VE",
    "tanzania, united republic of": "TZ",
    "moldova, republic of": "MD",
    "türkiye": "TR",
    "turkiye": "TR",
    "czech republic": "CZ",
    "macedonia": "MK",
}

# Lazily-built normalized canonical-name/alias -> code index.
_NAME_INDEX: Optional[dict[str, str]] = None


def _country_lookup_key(value: str) -> str:
    """Normalize country names for case- and accent-insensitive lookup."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.split())


def _name_index() -> dict[str, str]:
    global _NAME_INDEX
    if _NAME_INDEX is None:
        index = {
            _country_lookup_key(entry["name"]): code
            for code, entry in COUNTRIES.items()
        }
        index.update(
            {_country_lookup_key(alias): code for alias, code in ALIASES.items()}
        )
        _NAME_INDEX = index
    return _NAME_INDEX


def resolve_country_code(value: Optional[str]) -> Optional[str]:
    """Resolve a free-text jurisdiction (country name, alias, or ISO code) to an
    ISO 3166-1 alpha-2 code. Returns None if it can't be matched."""
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    # Direct ISO code (case-insensitive)
    upper = raw.upper()
    if upper in COUNTRIES:
        return upper
    # Name or alias (case- and accent-insensitive), tolerate a leading
    # "jurisdiction:" label.
    if raw.casefold().startswith("jurisdiction:"):
        raw = raw.split(":", 1)[1].strip()
        iso = raw.upper()
        if iso in COUNTRIES:
            return iso
    return _name_index().get(_country_lookup_key(raw))


class RegionAncestors(TypedDict):
    country_code: Optional[str]
    subregion_code: Optional[str]
    region_code: Optional[str]


def region_ancestors(country_code: Optional[str]) -> RegionAncestors:
    """Return the {country, subregion, region} M49 ancestor codes for a country code.
    Used to match a point (the user's country) against resource coverage scopes."""
    if not country_code:
        return {"country_code": None, "subregion_code": None, "region_code": None}
    code = country_code.upper()
    entry = COUNTRIES.get(code)
    if not entry:
        return {"country_code": code, "subregion_code": None, "region_code": None}
    subregion = entry["subregion"]
    return {
        "country_code": code,
        "subregion_code": subregion,
        "region_code": _SUBREGION_TO_REGION.get(subregion),
    }


def iter_country_region_rows() -> Iterator[tuple[str, str, Optional[str], Optional[str], Optional[str], Optional[str]]]:
    """Yield (country_code, country_name, subregion_code, subregion_name,
    region_code, region_name) tuples for seeding the country_regions table."""
    for code, entry in COUNTRIES.items():
        subregion = entry["subregion"]
        region = _SUBREGION_TO_REGION.get(subregion)
        yield (
            code,
            entry["name"],
            subregion,
            SUBREGION_NAMES.get(subregion),
            region,
            REGION_NAMES.get(region) if region else None,
        )


def describe_scope(scope_level: Optional[str], scope_code: Optional[str]) -> str:
    """Human-readable label for a resource's coverage scope (for display/context)."""
    if scope_level == "global":
        return "Global"
    if scope_level == "country" and scope_code:
        entry = COUNTRIES.get(scope_code.upper())
        return entry["name"] if entry else scope_code
    if scope_level == "subregion" and scope_code:
        return SUBREGION_NAMES.get(scope_code, scope_code)
    if scope_level == "region" and scope_code:
        return REGION_NAMES.get(scope_code, scope_code)
    return scope_code or "Unknown"


def is_valid_scope(scope_level: Optional[str], scope_code: Optional[str]) -> bool:
    """Validate a (scope_level, scope_code) pair against the known taxonomy."""
    if scope_level == "global":
        return not scope_code
    if scope_level == "country":
        return bool(scope_code) and scope_code.upper() in COUNTRIES
    if scope_level == "subregion":
        return bool(scope_code) and scope_code in SUBREGION_NAMES
    if scope_level == "region":
        return bool(scope_code) and scope_code in REGION_NAMES
    return False
