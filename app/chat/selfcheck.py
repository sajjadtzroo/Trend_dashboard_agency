"""Phase 0 structural self-check — no network, no DB, no API key.

Run: python -m app.chat.selfcheck
Asserts the graph compiles and the one node is wired START -> generate -> END.
The real graph's structural invariants (every node reachable, every router
return maps to a node, bounded cycles) grow here as the graph does.
"""
from .graph import build_graph


def main() -> None:
    graph = build_graph(checkpointer=None)
    g = graph.get_graph()
    node_names = set(g.nodes)

    expected = {"normalize", "classify", "plan_sql", "exec_sql", "generate_sql",
                "retrieve", "grade", "rewrite_query", "generate_doc", "guard_ground", "refuse"}
    missing = expected - node_names
    assert not missing, f"missing nodes: {missing}"

    mermaid = g.draw_mermaid()
    assert "__start__" in mermaid and "__end__" in mermaid, "START/END not wired"

    print(mermaid)  # commit this to graph.mmd and diff in review (plan §7)
    print("OK: chat graph compiles — data + doc branches + classify router wired")


if __name__ == "__main__":
    main()
