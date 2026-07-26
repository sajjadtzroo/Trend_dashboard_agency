"""Pure cell-cleaning helpers — no DB, unit-testable (see __main__)."""
import math

_ERRORS = {"", "-", "#DIV/0!", "#N/A", "#VALUE!", "#REF!", "NULL", "NA", "N/A"}


def clean_text(v):
    """Strip whitespace/tabs; empty -> None."""
    if v is None:
        return None
    s = str(v).replace("\t", " ").strip()
    return s or None


def clean_number(v):
    """Strip thousands separators / %, map error strings & blanks -> None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else float(v)
    s = str(v).replace("\t", "").replace(",", "").strip()
    if s.upper() in _ERRORS:
        return None
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        return float(s)
    except ValueError:
        return None


COMPANY_ALIASES = {"bel": "Bel Rouzaneh"}   # lowercase key -> canonical company name
BRAND_ALIASES = {"kibi": "Kibi"}            # collapse casing variants (Kibi/KIBI)


def canon_company(v):
    """Canonicalise a company name so spelling/casing variants collapse to one dim_client."""
    s = clean_text(v)
    return COMPANY_ALIASES.get(s.lower(), s) if s else None


def canon_brand(v):
    """Canonicalise a brand name (collapse casing variants) before dim_brand upsert."""
    s = clean_text(v)
    return BRAND_ALIASES.get(s.lower(), s) if s else None


def clean_percent(v):
    """Normalise a percentage to 0..100 numeric. '90%'/90/0.9 -> 90.0. Errors -> None."""
    n = clean_number(v)
    if n is None:
        return None
    if 0 < abs(n) <= 1:          # 0.9 -> 90 ; leaves exact 1.0 as 1 (ambiguous, treat as 100)
        n = n * 100
    return round(n, 2)


if __name__ == "__main__":
    assert clean_number("10,000,000,000") == 1e10
    assert clean_number("#DIV/0!") is None
    assert clean_number("90%") == 90.0
    assert clean_number("  1,234.5 ") == 1234.5
    assert clean_number(float("nan")) is None
    assert clean_text("  Snapp\tMarket ") == "Snapp Market"
    assert clean_text("") is None
    assert clean_percent("90%") == 90.0
    assert clean_percent(0.9) == 90.0
    assert clean_percent(90) == 90.0
    assert clean_percent("#DIV/0!") is None
    assert canon_company("BEL") == "Bel Rouzaneh"
    assert canon_company("Bel Rouzaneh") == "Bel Rouzaneh"
    assert canon_company("Snapp Market") == "Snapp Market"   # unknown -> passthrough
    assert canon_company("  ") is None
    assert canon_brand("KIBI") == "Kibi" and canon_brand("Kibi") == "Kibi"
    assert canon_brand("Rouzaneh") == "Rouzaneh"
    print("clean.py ok")
