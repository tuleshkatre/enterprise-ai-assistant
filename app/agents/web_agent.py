from time import perf_counter

from ddgs import DDGS

from app.observability.langsmith import add_trace_metadata


def web_agent(state):

    query = state.get("resolved_query") or state["query"]
    started_at = perf_counter()

    try:
        with DDGS(timeout=3) as ddgs:
            results = list(ddgs.text(query, max_results=5))

        formatted_results = [
            {
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", ""),
            }
            for r in results
        ]

        web_search_ms = (perf_counter() - started_at) * 1000
        add_trace_metadata(
            web_query=query,
            web_result_count=len(formatted_results),
            web_search_ms=web_search_ms,
            urls=[result["url"] for result in formatted_results],
        )
        return {
            "web_output": {"query": query, "results": formatted_results},
            "performance_metrics": {"web_search_ms": web_search_ms},
            "observability": {
                "web_query": query,
                "web_result_count": len(formatted_results),
            },
        }

    except Exception as e:
        web_search_ms = (perf_counter() - started_at) * 1000
        add_trace_metadata(
            web_query=query,
            web_result_count=0,
            web_search_ms=web_search_ms,
            web_error_type=type(e).__name__,
        )
        return {
            "web_output": {"query": query, "error": str(e), "results": []},
            "performance_metrics": {"web_search_ms": web_search_ms},
            "observability": {
                "web_query": query,
                "web_result_count": 0,
                "web_error_type": type(e).__name__,
            },
        }
