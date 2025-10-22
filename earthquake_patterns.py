"""
Earthquake pattern matching for Turkish başlıks
Matches format: [day] [month] [year] [province] (deprem/depremi)
Example: "6 şubat 2025 kahramanmaraş depremi"
"""
import re
from typing import Optional, Dict
from datetime import datetime, timedelta

# 81 Turkish provinces (official)
PROVINCES = [
    "adana", "adıyaman", "afyonkarahisar", "ağrı", "aksaray", "amasya", "ankara",
    "antalya", "ardahan", "artvin", "aydın", "balıkesir", "bartın", "batman",
    "bayburt", "bilecik", "bingöl", "bitlis", "bolu", "burdur", "bursa",
    "çanakkale", "çankırı", "çorum", "denizli", "diyarbakır", "düzce", "edirne",
    "elazığ", "erzincan", "erzurum", "eskişehir", "gaziantep", "giresun",
    "gümüşhane", "hakkâri", "hatay", "ığdır", "isparta", "istanbul", "i̇stanbul",
    "izmir", "i̇zmir", "kahramanmaraş", "karabük", "karaman", "kars", "kastamonu",
    "kayseri", "kilis", "kırıkkale", "kırklareli", "kırşehir", "kocaeli", "konya",
    "kütahya", "malatya", "manisa", "mardin", "mersin", "muğla", "muş", "nevşehir",
    "niğde", "ordu", "osmaniye", "rize", "sakarya", "samsun", "siirt", "sinop",
    "sivas", "şanlıurfa", "şırnak", "tekirdağ", "tokat", "trabzon", "tunceli",
    "uşak", "van", "yalova", "yozgat", "zonguldak",
    # ASCII variants (without Turkish characters)
    "adiyaman", "afyon", "agri", "aydin", "balikesir", "bartin", "bayburt",
    "bingol", "canakkale", "cankiri", "corum", "diyarbakir", "duzce", "elazig",
    "gumushane", "hakkari", "igdir", "kahramanmaras", "karabuk", "kirikkale",
    "kirklareli", "kirsehir", "kutahya", "mugla", "mus", "nigde", "sanliurfa",
    "sirnak", "tekirdag"
]

# Turkish months
MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
    "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12
}

# Common earthquake keywords
EARTHQUAKE_KEYWORDS = ["deprem", "depremi"]


def normalize_turkish(text: str) -> str:
    """Normalize Turkish text for matching (lowercase, handle special chars)"""
    text = text.lower()
    # Common replacements for matching
    replacements = {
        'ı': 'i',
        'ğ': 'g',
        'ü': 'u',
        'ş': 's',
        'ö': 'o',
        'ç': 'c',
        'İ': 'i',
        'Ğ': 'g',
        'Ü': 'u',
        'Ş': 's',
        'Ö': 'o',
        'Ç': 'c'
    }
    normalized = text
    for tr_char, en_char in replacements.items():
        normalized = normalized.replace(tr_char, en_char)
    return normalized


def is_date_current(day: int, month: int, year: int, tolerance_days: int = 1) -> bool:
    """
    Check if extracted date is within tolerance window from current date
    tolerance_days: ±N days from current date (default ±1 day)

    Returns True if date is current, False if too old/future
    """
    try:
        extracted_date = datetime(year, month, day).date()
        current_date = datetime.now().date()

        # Calculate time difference in days
        time_diff = abs((extracted_date - current_date).days)

        return time_diff <= tolerance_days
    except ValueError:
        # Invalid date (e.g., February 30)
        return False


def is_earthquake_baslik(title: str) -> Optional[Dict]:
    """
    Check if başlık title matches earthquake pattern
    Pattern: [day] [month] [year] [province] (optional: deprem/depremi)

    Returns dict with extracted info if match, None otherwise
    """
    title_lower = title.lower()
    title_normalized = normalize_turkish(title)

    # Pattern: day (1-31) + month name + year (2000-2099) + province
    # Example: "6 şubat 2025 kahramanmaraş depremi"

    # Check for day (1-31)
    day_match = re.search(r'\b([1-9]|[12][0-9]|3[01])\b', title)
    if not day_match:
        return None

    day = int(day_match.group(1))

    # Check for month
    month = None
    month_name = None
    for month_str, month_num in MONTHS.items():
        if month_str in title_lower:
            month = month_num
            month_name = month_str
            break

    if not month:
        return None

    # Check for year (2000-2099)
    year_match = re.search(r'\b(20\d{2})\b', title)
    if not year_match:
        return None

    year = int(year_match.group(1))

    # Temporal validation: date must be within ±1 day of current date
    if not is_date_current(day, month, year, tolerance_days=1):
        return None

    # Check for province (use word boundaries to avoid false matches)
    found_province = None
    for province in PROVINCES:
        province_normalized = normalize_turkish(province)
        # Use regex with word boundaries to match whole words only
        pattern = r'\b' + re.escape(province) + r'\b'
        pattern_normalized = r'\b' + re.escape(province_normalized) + r'\b'

        if re.search(pattern, title_lower) or re.search(pattern_normalized, title_normalized):
            found_province = province
            break

    if not found_province:
        return None

    # Check if earthquake keyword is present (optional but increases confidence)
    has_earthquake_keyword = any(kw in title_lower for kw in EARTHQUAKE_KEYWORDS)

    return {
        'day': day,
        'month': month,
        'month_name': month_name,
        'year': year,
        'province': found_province,
        'has_earthquake_keyword': has_earthquake_keyword,
        'confidence': 'high' if has_earthquake_keyword else 'medium'
    }


def test_patterns():
    """Test the pattern matcher with sample başlıks"""
    current_date = datetime.now()
    print(f"Current date: {current_date.strftime('%d %B %Y')} (testing with ±1 day tolerance)")
    print()

    test_cases = [
        # Current dates (should match)
        "22 ekim 2025 istanbul depremi",  # Today
        "21 ekim 2025 mardin depremi",  # Yesterday (within ±1 day)
        "23 ekim 2025 ankara sarsıntısı",  # Tomorrow (within ±1 day)

        # Old dates (should NOT match due to temporal filter)
        "6 şubat 2025 kahramanmaraş depremi",  # Months old
        "15 mart 2024 van sarsıntısı",  # Year old
        "1 ocak 2023 hatay",  # Years old

        # Non-earthquake posts (should NOT match)
        "gram altın",
        "21 ekim 2025 mattia ahmet minguzzi davası",

        # Edge cases for current earthquakes with different formats
        "22 ekim 2025 istanbul deprem",  # Missing 'i' suffix
        "22 ekim 2025 istanbul depremi Erdoğan açıklaması",  # Has extra context
    ]

    print("Testing earthquake pattern matcher:")
    print("-" * 80)
    for title in test_cases:
        result = is_earthquake_baslik(title)
        if result:
            print(f"✓ MATCH: {title}")
            print(f"  → {result['day']} {result['month_name']} {result['year']} - {result['province']}")
            print(f"  → Confidence: {result['confidence']}")
        else:
            print(f"✗ NO MATCH: {title}")
        print()


if __name__ == "__main__":
    test_patterns()
