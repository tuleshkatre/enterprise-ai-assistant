from app.graph.workflow import graph, stream_graph

EXPECTED_SHARED_NODES = {
    "context_resolver",
    "supervisor",
    "document",
    "rewrite",
    "retrieve",
    "web",
    "calculator",
    "sql",
    "conversation",
    "memory",
}


def test_normal_and_stream_graphs_have_route_parity():
    normal_nodes = set(graph.get_graph().nodes)
    stream_nodes = set(stream_graph.get_graph().nodes)

    assert EXPECTED_SHARED_NODES <= normal_nodes
    assert EXPECTED_SHARED_NODES <= stream_nodes
    assert "response" in normal_nodes
    assert "response_stream" in stream_nodes
    assert normal_nodes - {"response"} == stream_nodes - {"response_stream"}
