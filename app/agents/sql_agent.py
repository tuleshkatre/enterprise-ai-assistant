import logging
import re
from datetime import date, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.observability.langsmith import add_trace_metadata
from app.rag.generator import llm
from app.rag.providers import extract_text_content

logger = logging.getLogger(__name__)

MAX_SQL_ROWS = 200
MAX_CELL_CHARS = 1000
ALLOWED_RELATIONS = {
    "tenant_conversations",
    "tenant_document_chunks",
    "tenant_messages",
}
BANNED_KEYWORDS = {
    "alter",
    "copy",
    "create",
    "delete",
    "do",
    "drop",
    "execute",
    "grant",
    "insert",
    "into",
    "merge",
    "prepare",
    "reindex",
    "revoke",
    "set",
    "truncate",
    "union",
    "update",
    "vacuum",
}
BANNED_FUNCTION_PATTERNS = (
    r"\bcurrent_setting\s*\(",
    r"\bdblink\w*\s*\(",
    r"\blo_\w+\s*\(",
    r"\bpg_\w+\s*\(",
    r"\bset_config\s*\(",
)
RELATION_PATTERN = re.compile(
    r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_.]*)",
    re.IGNORECASE,
)
WORD_PATTERN = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b")

SQL_SCHEMA = """Available tenant-scoped relations:
- tenant_conversations(id, title, created_at)
- tenant_document_chunks(id, filename, page_number, chunk_index)
- tenant_messages(id, conversation_id, role, content, created_at)

Relationships:
- tenant_messages.conversation_id = tenant_conversations.id"""

TENANT_SCOPE_CTES = """WITH
tenant_conversations AS (
    SELECT id, title, created_at
    FROM conversations
    WHERE user_id = :user_id
),
tenant_document_chunks AS (
    SELECT id, filename, page_number, chunk_index
    FROM document_chunks
    WHERE user_id = :user_id
),
tenant_messages AS (
    SELECT m.id, m.conversation_id, m.role, m.content, m.created_at
    FROM messages AS m
    JOIN conversations AS c ON c.id = m.conversation_id
    WHERE c.user_id = :user_id
)
"""


class UnsafeSQLQuery(ValueError):
    """Raised when generated SQL falls outside the read-only policy."""


def build_sql_generation_prompt(query: str) -> str:
    return f"""
You translate enterprise analytics questions into PostgreSQL SELECT queries.

{SQL_SCHEMA}

Rules:
- Return exactly one SELECT query and no markdown or explanation.
- Use only the listed tenant-scoped relations and columns.
- Never query base tables or PostgreSQL system catalogs.
- Never use SELECT *, UNION, comments, or multiple statements.
- Never modify data or database structure.
- Use clear snake_case aliases for calculated columns.
- Use PostgreSQL syntax.

Examples:
- "How many documents have I uploaded?"
  SELECT COUNT(DISTINCT filename) AS document_count FROM tenant_document_chunks
- "Count document chunks by filename"
  SELECT filename, COUNT(*) AS chunk_count FROM tenant_document_chunks GROUP BY filename
- "Group messages by role"
  SELECT role, COUNT(*) AS message_count FROM tenant_messages GROUP BY role
- "How many messages are in each conversation?"
  SELECT conversation_id, COUNT(*) AS message_count FROM tenant_messages GROUP BY conversation_id
- "List my five most recent conversations"
  SELECT id, title, created_at FROM tenant_conversations ORDER BY created_at DESC LIMIT 5

User question:
{query}
"""


def known_safe_query(question: str) -> str | None:
    """Use deterministic SQL for high-confidence common analytics intents."""
    normalized = " ".join(question.casefold().split())
    if (
        re.search(r"\b(list|show)\b", normalized)
        and re.search(r"\b(recent|latest)\b", normalized)
        and re.search(r"\bconversations?\b", normalized)
    ):
        limit_match = re.search(r"\b(\d+)\b", normalized)
        limit = min(int(limit_match.group(1)), 20) if limit_match else 5
        return (
            "SELECT id, title, created_at FROM tenant_conversations "
            f"ORDER BY created_at DESC LIMIT {limit}"
        )
    return None


def _strip_code_fence(value: str) -> str:
    sql = value.strip()
    if sql.startswith("```") and sql.endswith("```"):
        sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        if sql.lower().startswith("sql\n"):
            sql = sql.split("\n", 1)[1].strip()
    return sql


def validate_select_sql(value: Any) -> str:
    if not isinstance(value, str):
        raise UnsafeSQLQuery("SQL generation did not return text")

    sql = _strip_code_fence(value)
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()

    lowered = sql.casefold()
    if not lowered.startswith("select "):
        raise UnsafeSQLQuery("Only SELECT statements are permitted")
    if ";" in sql or "--" in sql or "/*" in sql or "*/" in sql:
        raise UnsafeSQLQuery("Comments and multiple statements are forbidden")
    if re.search(r"\bselect\s+\*", lowered):
        raise UnsafeSQLQuery("SELECT * is forbidden")

    words = {word.casefold() for word in WORD_PATTERN.findall(sql)}
    blocked = words & BANNED_KEYWORDS
    if blocked:
        raise UnsafeSQLQuery("Generated SQL contains a forbidden operation")
    if any(re.search(pattern, lowered) for pattern in BANNED_FUNCTION_PATTERNS):
        raise UnsafeSQLQuery("Generated SQL contains an unsafe function")

    relations = {relation.casefold() for relation in RELATION_PATTERN.findall(sql)}
    if not relations or not relations <= ALLOWED_RELATIONS:
        raise UnsafeSQLQuery("Generated SQL references a forbidden relation")

    return sql


def validate_question_alignment(question: str, sql: str) -> None:
    """Reject structurally valid SQL that does not satisfy clear analytics intent."""
    normalized_question = question.casefold()
    normalized_sql = sql.casefold()
    asks_for_grouping = (
        re.search(r"\b(group|each|per)\b", normalized_question) is not None
    )
    asks_for_count = (
        re.search(r"\b(count|how many|number of)\b", normalized_question) is not None
    )
    if asks_for_grouping and "group by" not in normalized_sql:
        raise UnsafeSQLQuery("Generated SQL omitted required grouping")
    if asks_for_count and "count(" not in normalized_sql:
        raise UnsafeSQLQuery("Generated SQL omitted required aggregation")


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_CELL_CHARS]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)[:MAX_CELL_CHARS]


def _structured_rows(result: Any) -> list[dict[str, Any]]:
    return [
        {str(key): _safe_value(value) for key, value in row.items()}
        for row in result.mappings().all()
    ]


def sql_agent(state: dict[str, Any]) -> dict[str, Any]:
    generation_started_at = perf_counter()
    query = state.get("resolved_query") or state["query"]
    generated_sql = known_safe_query(query)
    generation_mode = "deterministic" if generated_sql is not None else "llm"
    if generated_sql is None:
        generated_sql = extract_text_content(
            llm.invoke(build_sql_generation_prompt(query)).content
        )
    sql_generation_ms = (perf_counter() - generation_started_at) * 1000

    try:
        safe_sql = validate_select_sql(generated_sql)
        validate_question_alignment(query, safe_sql)
    except UnsafeSQLQuery:
        logger.warning("sql_agent validation_failed=true")
        add_trace_metadata(
            sql_generation_mode=generation_mode,
            generated_sql=str(generated_sql),
            sql_validation_status="rejected",
            sql_generation_ms=sql_generation_ms,
            sql_execution_ms=0.0,
            sql_row_count=0,
        )
        return {
            "sql_output": [],
            "sql_error": "The database question could not be executed safely.",
            "performance_metrics": {
                "sql_generation_ms": sql_generation_ms,
                "sql_execution_ms": 0.0,
            },
            "observability": {
                "sql_generation_mode": generation_mode,
                "sql_validation_status": "rejected",
                "sql_row_count": 0,
            },
        }

    execution_started_at = perf_counter()
    bounded_query = (
        f"{TENANT_SCOPE_CTES}\n"
        f"SELECT * FROM ({safe_sql}) AS sql_agent_result "
        f"LIMIT {MAX_SQL_ROWS}"
    )
    try:
        result = state["db"].execute(text(bounded_query), {"user_id": state["user_id"]})
        rows = _structured_rows(result)
        sql_error = None
    except SQLAlchemyError:
        logger.exception("sql_agent execution_failed=true")
        rows = []
        sql_error = "The database question could not be completed."

    sql_execution_ms = (perf_counter() - execution_started_at) * 1000
    logger.info(
        "sql_timing generation_ms=%.2f execution_ms=%.2f row_count=%d",
        sql_generation_ms,
        sql_execution_ms,
        len(rows),
    )
    add_trace_metadata(
        sql_generation_mode=generation_mode,
        generated_sql=safe_sql,
        sql_validation_status="accepted",
        sql_generation_ms=sql_generation_ms,
        sql_execution_ms=sql_execution_ms,
        sql_row_count=len(rows),
        sql_execution_status="error" if sql_error else "success",
    )
    return {
        "sql_output": rows,
        "sql_error": sql_error,
        "performance_metrics": {
            "sql_generation_ms": sql_generation_ms,
            "sql_execution_ms": sql_execution_ms,
        },
        "observability": {
            "sql_generation_mode": generation_mode,
            "sql_validation_status": "accepted",
            "sql_execution_status": "error" if sql_error else "success",
            "sql_row_count": len(rows),
        },
    }
