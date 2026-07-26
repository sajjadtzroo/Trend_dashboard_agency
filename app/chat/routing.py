"""Pure routing predicates for the graph (plan §6).

No I/O, no LLM — functions of state, testable as a truth table. The routing decision
that needs a model (doc vs data) is made by the `classify` node, which writes `route`;
these routers only READ it. That keeps routing testable as a truth table.
"""

MAX_SQL_ATTEMPTS = 2
MAX_RETRIEVE_ATTEMPTS = 2
_ROUTES = ("doc", "data", "refuse")


def route(state: dict) -> str:
    """classify -> retrieve (doc) / plan_sql (data) / refuse. Fail closed on anything odd."""
    r = state.get("route")
    return r if r in _ROUTES else "refuse"


def after_plan(state: dict) -> str:
    """plan_sql -> exec_sql if we got a query, else -> generate (refusal / out of scope)."""
    return "exec_sql" if state.get("sql") else "generate"


def after_exec(state: dict) -> str:
    """exec_sql -> retry plan_sql on error within the bound, else -> generate."""
    if state.get("sql_error") and state.get("sql_attempts", 0) < MAX_SQL_ATTEMPTS:
        return "plan_sql"
    return "generate"


def after_grade(state: dict) -> str:
    """grade -> generate if sufficient; else rewrite within the bound, else generate anyway."""
    if state.get("sufficient"):
        return "generate"
    if state.get("retrieve_attempts", 0) < MAX_RETRIEVE_ATTEMPTS:
        return "rewrite"
    return "generate"


def after_guard(state: dict) -> str:
    """guard_ground -> end if grounded, else -> refuse (fail closed)."""
    return "ok" if state.get("grounded") else "refuse"


if __name__ == "__main__":
    # route
    assert route({"route": "doc"}) == "doc"
    assert route({"route": "data"}) == "data"
    assert route({"route": "refuse"}) == "refuse"
    assert route({"route": "garbage"}) == "refuse"   # fail closed
    assert route({}) == "refuse"
    # after_plan
    assert after_plan({"sql": "SELECT 1"}) == "exec_sql"
    assert after_plan({"sql": None}) == "generate"
    assert after_plan({}) == "generate"
    # after_exec — every branch incl. fallthrough
    assert after_exec({"sql_error": "boom", "sql_attempts": 1}) == "plan_sql"
    assert after_exec({"sql_error": "boom", "sql_attempts": 2}) == "generate"  # bound hit
    assert after_exec({"sql_error": None, "sql_attempts": 1}) == "generate"    # success
    assert after_exec({}) == "generate"
    # after_grade — every branch incl. bound
    assert after_grade({"sufficient": True}) == "generate"
    assert after_grade({"sufficient": False, "retrieve_attempts": 1}) == "rewrite"
    assert after_grade({"sufficient": False, "retrieve_attempts": 2}) == "generate"  # bound hit
    assert after_grade({}) == "rewrite"               # unsure + attempt 0 -> try rewriting
    # after_guard
    assert after_guard({"grounded": True}) == "ok"
    assert after_guard({"grounded": False}) == "refuse"
    assert after_guard({}) == "refuse"                # fail closed
    print("routing truth table OK")
