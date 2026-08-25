from app.services.graph_chat_service import (
    TIMING_FIELDS,
    _complete_performance_metrics,
)


def test_request_trace_always_contains_every_performance_metric():
    metrics = _complete_performance_metrics({"rewrite_ms": 12.5})

    assert set(metrics) == set(TIMING_FIELDS)
    assert metrics["rewrite_ms"] == 12.5
    assert metrics["embedding_ms"] == 0.0
    assert metrics["retrieval_ms"] == 0.0
    assert metrics["rerank_ms"] == 0.0
    assert metrics["answer_llm_ms"] == 0.0
    assert metrics["sql_generation_ms"] == 0.0
    assert metrics["sql_execution_ms"] == 0.0
    assert metrics["total_request_ms"] == 0.0
