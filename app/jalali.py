"""Jalali <-> Gregorian helpers and dim_date upsert."""
from functools import lru_cache
import jdatetime
from sqlalchemy import text

MONTHS_FA = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


@lru_cache(maxsize=4096)
def to_gregorian(year: int, month: int, day: int):
    # ponytail: in-process memoization — pure date math called once per import row,
    # with the same (y,m,d) recurring heavily. Redis would be absurd overhead here.
    return jdatetime.date(year, month, day).togregorian()


def date_key(year: int, month: int, day: int) -> int:
    return year * 10000 + month * 100 + day


def upsert_date(db, year, month, day) -> int | None:
    """Get-or-create dim_date; returns date_key. Missing day defaults to 1."""
    if not year or not month:
        return None
    if not day:
        day = 1  # caller logs this
    year, month, day = int(year), int(month), int(day)
    key = date_key(year, month, day)
    greg = to_gregorian(year, month, day)
    db.execute(text("""
        INSERT INTO dim_date (date_key, jalali_year, jalali_month, jalali_day, jalali_date,
                              gregorian_date, jalali_quarter, jalali_month_name_fa)
        VALUES (:k, :y, :m, :d, :jd, :g, :q, :fa)
        ON CONFLICT (date_key) DO NOTHING
    """), {"k": key, "y": year, "m": month, "d": day,
           "jd": f"{year:04d}-{month:02d}-{day:02d}", "g": greg,
           "q": (month - 1) // 3 + 1, "fa": MONTHS_FA[month - 1]})
    return key
