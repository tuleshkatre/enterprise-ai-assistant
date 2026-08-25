# LangSmith Audit

## Verdict

Current readiness: **4.5/10**

Tracing is enabled and most graph agents are decorated, but observability is not yet production-ready. No application code was changed during this audit.

## What Works

- Router decision appears in agent output.
- Rewrite output and `rewrite_ms` are captured.
- Retrieved documents and retrieval metrics are available.
- Web results contain titles, snippets, and URLs.
- SQL generation/execution metrics are captured.
- Response prompts are visible through LLM child runs.
- Normal and streaming graphs contain equivalent routes.

## Main Gaps

- LangSmith API connection currently fails with an SSL certificate verification error.
- Router latency is not measured.
- Reranker has no dedicated trace.
- Retrieved/reranked counts are logged but not structured trace metadata.
- Memory and summary retrieval happen outside traced graph nodes.
- Memory operations do not expose structured action/result metadata.
- Deterministic SQL is not visible internally in traces.
- Web latency and result count are missing.
- Response context size, selected document IDs, source count, and retry status are missing.
- `total_request_ms` is logged after graph completion and is not included in the graph trace.
- Manual `@traceable` decorators can duplicate LangGraph node spans.
- Raw state can expose history, memories, document chunks, SQL rows, and large payloads.
- Decorators use `project=`; installed LangSmith expects `project_name=`.

## Files Requiring Changes

- `app/config.py`
- `app/observability/langsmith.py` (new)
- `app/agents/agent_state.py`
- `app/agents/supervisor_agent.py`
- `app/agents/rewrite_agent.py`
- `app/agents/retrieve_agent.py`
- `app/rag/retrieval.py`
- `app/rag/reranker.py`
- `app/agents/web_agent.py`
- `app/agents/sql_agent.py`
- `app/agents/memory_agent.py`
- `app/services/conversation_memory_service.py`
- `app/services/graph_chat_service.py`
- `app/agents/response_agent.py`
- `app/agents/response_stream_agent.py`

## Recommended Implementation

1. Fix the Python/Requests CA trust store; do not disable TLS verification.
2. Add sanitized LangSmith input/output processors.
3. Redact memory values and bound history, chunks, web snippets, and SQL rows.
4. Add structured counts, IDs, route decisions, operation outcomes, and timings.
5. Add request-level root traces for normal and streaming workflows.
6. Trace memory retrieval, summary retrieval/generation, and reranking separately.
7. Add streaming time-to-first-token and parity tests.

Production should default to:

```env
LANGSMITH_CAPTURE_CONTENT=false
```

Controlled debugging may enable prompt/content capture temporarily.

## Expected Result

After these changes and successful dashboard validation, expected readiness is **8.5/10**. Remaining work will be LangSmith retention, access-control, and production privacy policy configuration.
