import re
from time import perf_counter

from app.observability.langsmith import add_trace_metadata

SQL_ENTITY_PATTERN = (
    r"conversations?|messages?|documents?|document\s+chunks?|"
    r"indexed\s+pages?"
)
SQL_ANALYTIC_PATTERN = re.compile(
    rf"\b(count|number\s+of|how\s+many|average|avg|minimum|maximum|"
    rf"group|breakdown|total|list|show)\b.*\b({SQL_ENTITY_PATTERN})\b",
    re.IGNORECASE,
)


def _is_sql_query(query: str) -> bool:
    return (
        re.search(r"\b(sql|database|database table)\b", query) is not None
        or SQL_ANALYTIC_PATTERN.search(query) is not None
    )


def supervisor_agent(state):
    started_at = perf_counter()
    print("SUPERVISOR RUNNING")

    query = state.get("resolved_query", state["query"]).lower().strip()

    if state.get("context_route") in {"conversation", "memory"}:
        route = state["context_route"]

    # Calculator Route

    elif re.search(r"\d+\s*[\+\-\*/]\s*\d+", query):
        route = "calculator"

    # SQL Route

    elif _is_sql_query(query):
        route = "sql"

    # Calculator Route

    elif (
        "calculate" in query
        or "sum" in query
        or "multiply" in query
        or "divide" in query
        or "percentage" in query
    ):
        route = "calculator"

    # Web Route

    elif any(
        word in query
        for word in [
            "latest",
            "today",
            "news",
            "current",
            "weather",
            "stock",
            "price",
            "market",
            "recent",
            "live",
        ]
    ):
        route = "web"

    # Default Document Route

    else:
        route = "document"

    print("=" * 50)
    print("QUERY :", query)
    print("ROUTE :", route)
    print("=" * 50)

    route_ms = (perf_counter() - started_at) * 1000
    add_trace_metadata(route=route, route_ms=route_ms, query=query)
    return {"route": route}
