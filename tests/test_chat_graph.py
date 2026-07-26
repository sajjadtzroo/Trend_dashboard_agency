"""Structural check of the chat graph — no network/LLM. Skips where langgraph
is not installed (e.g. host without the RAG deps); runs in the api container."""
import pytest

pytest.importorskip("langgraph", reason="langgraph not installed")


@pytest.mark.chatgraph
def test_graph_compiles_with_expected_nodes():
    from app.chat.graph import build_graph
    g = build_graph(checkpointer=None).get_graph()
    nodes = set(g.nodes)
    expected = {"normalize", "classify", "plan_sql", "exec_sql", "generate_sql",
                "retrieve", "grade", "rewrite_query", "generate_doc", "guard_ground", "refuse"}
    assert expected <= nodes, f"missing: {expected - nodes}"


@pytest.mark.chatgraph
def test_graph_has_start_and_end():
    from app.chat.graph import build_graph
    mermaid = build_graph(checkpointer=None).get_graph().draw_mermaid()
    assert "__start__" in mermaid and "__end__" in mermaid
