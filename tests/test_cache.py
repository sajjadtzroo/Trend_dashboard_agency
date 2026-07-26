"""app/cache.py — key building, JSON default, cached(), jobs. Uses real Redis."""
from decimal import Decimal
import pytest
from app import cache
from conftest import requires_services


class TestJsonDefault:
    def test_decimal_to_float(self):
        v = cache._json_default(Decimal("2.5"))
        assert v == 2.5 and isinstance(v, float)

    def test_other_to_str(self):
        assert cache._json_default({1, 2}) == str({1, 2})


class TestKey:
    def test_sorted_and_prefixed(self):
        assert cache._key("kpis", {"b": 2, "a": 1}) == "agg:kpis:a=1&b=2"

    def test_none_values_skipped(self):
        assert cache._key("x", {"a": None, "b": 3}) == "agg:x:b=3"

    def test_empty_params(self):
        assert cache._key("x", {}) == "agg:x:"


@requires_services
class TestCached:
    def test_miss_computes_then_hit_serves(self):
        calls = {"n": 0}

        def producer():
            calls["n"] += 1
            return {"v": 1}

        params = {"probe": "cache-test"}
        cache._r.delete(cache._key("unit", params))
        assert cache.cached("unit", params, producer) == {"v": 1}   # miss
        assert cache.cached("unit", params, producer) == {"v": 1}   # hit
        assert calls["n"] == 1                                       # producer ran once
        cache._r.delete(cache._key("unit", params))

    def test_decimal_survives_as_number(self):
        params = {"probe": "cache-decimal"}
        cache._r.delete(cache._key("unit", params))
        cache.cached("unit", params, lambda: {"n": Decimal("3.5")})   # store
        hit = cache.cached("unit", params, lambda: {"n": Decimal("3.5")})
        assert hit["n"] == 3.5 and isinstance(hit["n"], float)
        cache._r.delete(cache._key("unit", params))


@requires_services
def test_invalidate_aggregates_clears(monkeypatch):
    cache.cached("unit", {"probe": "inv"}, lambda: {"v": 1})
    assert cache._r.get(cache._key("unit", {"probe": "inv"})) is not None
    cache.invalidate_aggregates()
    assert cache._r.get(cache._key("unit", {"probe": "inv"})) is None


@requires_services
class TestJobs:
    def test_set_get_roundtrip(self):
        cache.set_job("t-job-1", {"status": "done", "n": 3})
        assert cache.get_job("t-job-1") == {"status": "done", "n": 3}
        cache._r.delete("job:t-job-1")

    def test_missing_job_none(self):
        assert cache.get_job("does-not-exist-xyz") is None
