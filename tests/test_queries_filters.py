"""app/queries.py (_coerce, rows) and app/filters.py (Filters, get_filters)."""
from decimal import Decimal
import pytest
from app.queries import _coerce, rows
from app.filters import Filters, get_filters
from conftest import requires_services


class TestCoerce:
    def test_decimal_to_float(self):
        v = _coerce(Decimal("12.50"))
        assert v == 12.5 and isinstance(v, float)

    def test_passthrough_types(self):
        assert _coerce(5) == 5
        assert _coerce("x") == "x"
        assert _coerce(None) is None


@requires_services
def test_rows_returns_list_of_dicts(db):
    out = rows(db, "SELECT 1 AS a, 'hi' AS b")
    assert out == [{"a": 1, "b": "hi"}]


@requires_services
def test_rows_coerces_numeric(db):
    out = rows(db, "SELECT CAST(3 AS NUMERIC) AS n")
    assert isinstance(out[0]["n"], float) and out[0]["n"] == 3.0


class TestWhere:
    def test_empty_no_clause(self):
        sql, p = Filters().where()
        assert sql == "" and p == {}

    def test_type_default_applied_when_unset(self):
        sql, p = Filters().where(type_default="SALE")
        assert "f.transaction_type = :ttype" in sql and p["ttype"] == "SALE"

    def test_explicit_type_overrides_default(self):
        sql, p = Filters(transaction_type="PAYABLE").where(type_default="SALE")
        assert p["ttype"] == "PAYABLE"

    def test_all_dimension_clauses(self):
        f = Filters(date_from=140401, date_to=140412, client="Unilever",
                    brand="Dove", service="VOD", user="Mamrez")
        sql, p = f.where()
        assert p == {"date_from": 140401, "date_to": 140412, "client": "Unilever",
                     "brand": "Dove", "service": "VOD", "user": "Mamrez"}
        assert sql.startswith(" WHERE ") and sql.count(" AND ") == 5

    def test_date_bounds_use_yyyymm_expression(self):
        sql, _ = Filters(date_from=140401).where()
        assert "(d.jalali_year*100 + d.jalali_month) >= :date_from" in sql


class TestAsParams:
    def test_roundtrips_all_fields(self):
        f = Filters(date_from=1, date_to=2, client="c", brand="b",
                    service="s", user="u", transaction_type="SALE")
        assert f.as_params() == {
            "date_from": 1, "date_to": 2, "client": "c", "brand": "b",
            "service": "s", "user": "u", "transaction_type": "SALE"}


def test_get_filters_builds_filters():
    f = get_filters(date_from=140401, client="Unilever")
    assert isinstance(f, Filters)
    assert f.date_from == 140401 and f.client == "Unilever"
