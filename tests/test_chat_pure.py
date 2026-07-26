"""Pure/deterministic chat helpers: normalize, routing truth table, rate guard.
LLM/graph pieces (graph, retrieval, embedder) need langgraph/OpenRouter — see
test_chat_graph.py which skips where those aren't installed."""
import pytest
from app.chat.normalize import normalize
from app.chat import routing
from conftest import requires_services


class TestNormalize:
    def test_persian_digits(self):
        assert normalize("۱۴۰۴") == "1404"

    def test_arabic_indic_digits(self):
        assert normalize("٠١٢") == "012"

    def test_arabic_letters_folded(self):
        assert normalize("كيان") == "کیان"      # Arabic kaf/yeh -> Persian

    def test_zwnj_removed(self):
        assert normalize("نیم‌فاصله") == "نیمفاصله"

    def test_whitespace_collapsed(self):
        assert normalize("a   b\t c") == "a b c"

    def test_idempotent(self):
        s = "سه‌ماهه اول ۱۴۰۴"
        assert normalize(normalize(s)) == normalize(s)

    def test_empty_passthrough(self):
        assert normalize("") == ""
        assert normalize(None) is None


class TestRoutingTruthTable:
    @pytest.mark.parametrize("state,exp", [
        ({"route": "doc"}, "doc"), ({"route": "data"}, "data"),
        ({"route": "refuse"}, "refuse"), ({"route": "garbage"}, "refuse"), ({}, "refuse"),
    ])
    def test_route(self, state, exp):
        assert routing.route(state) == exp

    @pytest.mark.parametrize("state,exp", [
        ({"sql": "SELECT 1"}, "exec_sql"), ({"sql": None}, "generate"), ({}, "generate"),
    ])
    def test_after_plan(self, state, exp):
        assert routing.after_plan(state) == exp

    @pytest.mark.parametrize("state,exp", [
        ({"sql_error": "boom", "sql_attempts": 1}, "plan_sql"),
        ({"sql_error": "boom", "sql_attempts": 2}, "generate"),   # bound hit
        ({"sql_error": None, "sql_attempts": 1}, "generate"),     # success
        ({}, "generate"),
    ])
    def test_after_exec(self, state, exp):
        assert routing.after_exec(state) == exp

    @pytest.mark.parametrize("state,exp", [
        ({"sufficient": True}, "generate"),
        ({"sufficient": False, "retrieve_attempts": 1}, "rewrite"),
        ({"sufficient": False, "retrieve_attempts": 2}, "generate"),  # bound hit
        ({}, "rewrite"),
    ])
    def test_after_grade(self, state, exp):
        assert routing.after_grade(state) == exp

    @pytest.mark.parametrize("state,exp", [
        ({"grounded": True}, "ok"), ({"grounded": False}, "refuse"), ({}, "refuse"),
    ])
    def test_after_guard(self, state, exp):
        assert routing.after_guard(state) == exp


@requires_services
class TestRateGuard:
    def test_disabled_when_limit_zero(self, monkeypatch):
        from app.chat import guards
        monkeypatch.setattr(guards, "RATE_LIMIT_PER_MIN", 0)
        assert guards.rate_limited("anyone") is False

    def test_trips_after_limit(self, monkeypatch):
        from app.chat import guards
        monkeypatch.setattr(guards, "RATE_LIMIT_PER_MIN", 3)
        cid = "unit-test-client"
        # clear both possible minute-window keys to avoid flakiness at the boundary
        import time
        for w in (int(time.time() // 60), int(time.time() // 60) - 1):
            guards._r.delete(f"rl:{cid}:{w}")
        results = [guards.rate_limited(cid) for _ in range(5)]
        assert results[:3] == [False, False, False]   # within limit
        assert results[3] is True                       # 4th trips
