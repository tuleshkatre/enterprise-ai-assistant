from operator import or_
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    query: str
    user_id: int
    conversation_id: int
    db: object

    history: str
    conversation_summary: str
    long_term_memories: list[dict[str, str]]
    current_message_id: int | None
    resolved_query: str
    context_route: str | None
    conversation_context: str
    conversation_answer: str
    retrieval_query: str

    route: str

    documents: list

    web_output: str

    calculator_output: str
    sql_output: list[dict[str, Any]]
    sql_error: str | None
    memory_output: str

    answer: str

    sources: list[dict[str, Any]]
    performance_metrics: Annotated[dict[str, float], or_]
    observability: Annotated[dict[str, Any], or_]
