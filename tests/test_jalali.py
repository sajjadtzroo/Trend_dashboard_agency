"""app/jalali.py — Jalali<->Gregorian + dim_date upsert (DB-backed, rolled back)."""
import datetime
import pytest
from sqlalchemy import text
from app.jalali import to_gregorian, date_key, upsert_date, MONTHS_FA
from conftest import requires_services


@pytest.mark.parametrize("y,m,d,greg", [
    (1404, 1, 1, "2025-03-21"),
    (1404, 5, 17, "2025-08-08"),
    (1403, 12, 29, "2025-03-19"),
])
def test_to_gregorian_known(y, m, d, greg):
    assert to_gregorian(y, m, d) == datetime.date.fromisoformat(greg)


def test_date_key_packs_yyyymmdd():
    assert date_key(1404, 5, 17) == 14040517
    assert date_key(1400, 1, 1) == 14000101


def test_months_fa_has_twelve():
    assert len(MONTHS_FA) == 12
    assert MONTHS_FA[0] == "فروردین"
    assert MONTHS_FA[11] == "اسفند"


class TestUpsertDate:
    def test_null_year_or_month_returns_none(self, db):
        assert upsert_date(db, None, 5, 1) is None
        assert upsert_date(db, 1404, None, 1) is None
        assert upsert_date(db, 0, 0, 0) is None

    @requires_services
    def test_missing_day_defaults_to_one(self, db):
        assert upsert_date(db, 1404, 6, None) == date_key(1404, 6, 1)

    @requires_services
    def test_idempotent_returns_same_key(self, db):
        k1 = upsert_date(db, 1399, 7, 3)
        k2 = upsert_date(db, 1399, 7, 3)
        assert k1 == k2 == date_key(1399, 7, 3)
        row = db.execute(text("SELECT jalali_month_name_fa, jalali_quarter, gregorian_date "
                              "FROM dim_date WHERE date_key=:k"), {"k": k1}).first()
        assert row[0] == MONTHS_FA[6]        # مهر
        assert row[1] == 3                    # month 7 -> Q3
        assert row[2] == to_gregorian(1399, 7, 3)
