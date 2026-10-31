"""Conservative salary range extraction from job advert text."""
import re

_RANGE = re.compile(
    r"(?P<currency>SEK|kr|USD|EUR|GBP|[$€£])?\s*"
    r"(?P<low>\d{1,3}(?:[,\s.]\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<low_k>k)?\s*"
    r"(?:-|–|—|to)\s*"
    r"(?P<currency2>SEK|kr|USD|EUR|GBP|[$€£])?\s*"
    r"(?P<high>\d{1,3}(?:[,\s.]\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<high_k>k)?\s*"
    r"(?P<currency3>SEK|kr|USD|EUR|GBP|[$€£])?",
    re.IGNORECASE,
)

_CURRENCIES = {"sek":"SEK","kr":"SEK","usd":"USD","$":"USD","eur":"EUR","€":"EUR","gbp":"GBP","£":"GBP"}

def _amount(value: str, thousands: bool) -> int:
    cleaned = re.sub(r"[^\d]", "", value)
    number = int(cleaned or "0")
    return number * 1000 if thousands else number

def extract_salary(text: str) -> dict:
    """Extract a plausible numeric range; return nulls rather than guessing."""
    for match in _RANGE.finditer(text or ""):
        currency_raw = match.group("currency") or match.group("currency2") or match.group("currency3") or ""
        currency = _CURRENCIES.get(currency_raw.casefold(), "")
        low = _amount(match.group("low"), bool(match.group("low_k")))
        high = _amount(match.group("high"), bool(match.group("high_k")))
        # Salary ranges below 1,000 are commonly bonuses/hourly fragments, not a reliable annual/monthly range.
        if 1000 <= low <= high <= 10_000_000:
            return {"salary_min": low, "salary_max": high, "salary_currency": currency}
    return {"salary_min": None, "salary_max": None, "salary_currency": ""}
