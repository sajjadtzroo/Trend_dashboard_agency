"""Unit tests for app/clean.py — pure cell cleaners, no DB."""
import math
from app.clean import clean_text, clean_number, canon_company, canon_brand, clean_percent


class TestCleanText:
    def test_strips_tabs_and_whitespace(self):
        assert clean_text("  Snapp\tMarket ") == "Snapp Market"

    def test_empty_and_none(self):
        assert clean_text("") is None
        assert clean_text("   ") is None
        assert clean_text(None) is None

    def test_number_coerced_to_str(self):
        assert clean_text(123) == "123"


class TestCleanNumber:
    def test_thousands_separator(self):
        assert clean_number("10,000,000,000") == 1e10

    def test_decimal_and_padding(self):
        assert clean_number("  1,234.5 ") == 1234.5

    def test_percent_suffix_stripped(self):
        assert clean_number("90%") == 90.0

    def test_error_strings_to_none(self):
        for e in ("#DIV/0!", "#N/A", "#VALUE!", "#REF!", "NULL", "N/A", "", "-"):
            assert clean_number(e) is None

    def test_nan_to_none(self):
        assert clean_number(float("nan")) is None

    def test_bool_is_none(self):
        # bool is an int subclass — must not become 1.0/0.0
        assert clean_number(True) is None
        assert clean_number(False) is None

    def test_numeric_passthrough(self):
        assert clean_number(5) == 5.0
        assert clean_number(3.14) == 3.14

    def test_unparseable_to_none(self):
        assert clean_number("abc") is None

    def test_none(self):
        assert clean_number(None) is None


class TestCanon:
    def test_company_alias(self):
        assert canon_company("BEL") == "Bel Rouzaneh"
        assert canon_company("bel") == "Bel Rouzaneh"

    def test_company_passthrough(self):
        assert canon_company("Snapp Market") == "Snapp Market"
        assert canon_company("Bel Rouzaneh") == "Bel Rouzaneh"

    def test_company_blank(self):
        assert canon_company("  ") is None
        assert canon_company(None) is None

    def test_brand_alias_casefold(self):
        assert canon_brand("KIBI") == "Kibi"
        assert canon_brand("Kibi") == "Kibi"

    def test_brand_passthrough(self):
        assert canon_brand("Rouzaneh") == "Rouzaneh"


class TestCleanPercent:
    def test_percent_string(self):
        assert clean_percent("90%") == 90.0

    def test_fraction_scaled(self):
        assert clean_percent(0.9) == 90.0

    def test_whole_number_kept(self):
        assert clean_percent(90) == 90.0

    def test_error_to_none(self):
        assert clean_percent("#DIV/0!") is None
        assert clean_percent(None) is None

    def test_rounds_two_dp(self):
        assert clean_percent(0.12345) == 12.35
