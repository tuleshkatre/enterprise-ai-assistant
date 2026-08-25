import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.agents import sql_agent as sql_module
from app.agents.sql_agent import (
    UnsafeSQLQuery,
    validate_question_alignment,
    validate_select_sql,
)


class _Response:
    def __init__(self, content: str):
        self.content = content


class _LLM:
    def __init__(self, sql: str):
        self.sql = sql

    def invoke(self, _prompt: str):
        return _Response(self.sql)


class _Mappings:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return _Mappings(self.rows)


class _DB:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        if self.error:
            raise self.error
        return _Result(self.rows)


@pytest.mark.parametrize(
    ("sql", "rows", "expected"),
    [
        (
            "SELECT COUNT(*) AS conversation_count FROM tenant_conversations",
            [{"conversation_count": 12}],
            [{"conversation_count": 12}],
        ),
        (
            "SELECT AVG(page_number) AS average_page FROM tenant_document_chunks",
            [{"average_page": 4.5}],
            [{"average_page": 4.5}],
        ),
        (
            "SELECT role, COUNT(*) AS message_count "
            "FROM tenant_messages GROUP BY role ORDER BY role",
            [
                {"role": "assistant", "message_count": 8},
                {"role": "user", "message_count": 8},
            ],
            [
                {"role": "assistant", "message_count": 8},
                {"role": "user", "message_count": 8},
            ],
        ),
    ],
)
def test_sql_agent_executes_safe_analytics(monkeypatch, sql, rows, expected):
    monkeypatch.setattr(sql_module, "llm", _LLM(sql))
    db = _DB(rows)

    result = sql_module.sql_agent(
        {"query": "analytics question", "db": db, "user_id": 42}
    )

    assert result["sql_output"] == expected
    assert result["sql_error"] is None
    assert result["performance_metrics"]["sql_generation_ms"] >= 0.0
    assert result["performance_metrics"]["sql_execution_ms"] >= 0.0
    assert db.calls[0][1] == {"user_id": 42}
    assert "WHERE user_id = :user_id" in db.calls[0][0]
    assert sql not in result.values()


def test_sql_agent_returns_empty_structured_result(monkeypatch):
    monkeypatch.setattr(
        sql_module,
        "llm",
        _LLM("SELECT id, title FROM tenant_conversations WHERE id = -1"),
    )

    result = sql_module.sql_agent(
        {"query": "missing conversation", "db": _DB(), "user_id": 1}
    )

    assert result["sql_output"] == []
    assert result["sql_error"] is None


@pytest.mark.parametrize(
    "unsafe_sql",
    [
        "INSERT INTO tenant_conversations(id) VALUES (1)",
        "UPDATE tenant_conversations SET title = 'x'",
        "DELETE FROM tenant_conversations",
        "DROP TABLE conversations",
        "ALTER TABLE conversations ADD COLUMN x text",
        "TRUNCATE TABLE conversations",
        "CREATE TABLE injected(id int)",
        "EXECUTE dangerous_plan",
        "SELECT id FROM tenant_conversations UNION SELECT id FROM users",
        "SELECT id FROM tenant_conversations; DROP TABLE conversations",
        "SELECT id FROM tenant_conversations -- bypass",
    ],
)
def test_validator_blocks_mutation_and_injection(unsafe_sql):
    with pytest.raises(UnsafeSQLQuery):
        validate_select_sql(unsafe_sql)


def test_non_existing_table_is_rejected_before_execution(monkeypatch):
    monkeypatch.setattr(sql_module, "llm", _LLM("SELECT id FROM employee_payroll"))
    db = _DB()

    result = sql_module.sql_agent({"query": "show payroll", "db": db, "user_id": 1})

    assert result["sql_output"] == []
    assert result["sql_error"] == (
        "The database question could not be executed safely."
    )
    assert db.calls == []


def test_grouping_intent_requires_group_by():
    with pytest.raises(UnsafeSQLQuery):
        validate_question_alignment(
            "Group messages by role",
            "SELECT role FROM tenant_messages",
        )


def test_count_intent_requires_count_aggregation():
    with pytest.raises(UnsafeSQLQuery):
        validate_question_alignment(
            "How many conversations do I have?",
            "SELECT id FROM tenant_conversations",
        )


def test_database_execution_error_is_not_exposed(monkeypatch):
    monkeypatch.setattr(
        sql_module,
        "llm",
        _LLM("SELECT id, title FROM tenant_conversations"),
    )
    db = _DB(error=SQLAlchemyError("relation internals and SQL text"))

    result = sql_module.sql_agent(
        {"query": "list conversations", "db": db, "user_id": 1}
    )

    assert result["sql_output"] == []
    assert result["sql_error"] == "The database question could not be completed."
    assert "internals" not in result["sql_error"]


def test_recent_conversations_use_deterministic_safe_query(monkeypatch):
    class _UnexpectedLLM:
        def invoke(self, _prompt):
            raise AssertionError("Known analytics intent must not call the LLM")

    monkeypatch.setattr(sql_module, "llm", _UnexpectedLLM())
    db = _DB([{"id": 1, "title": "Leave policy", "created_at": "now"}])

    result = sql_module.sql_agent(
        {
            "query": "List my five most recent conversations",
            "db": db,
            "user_id": 1,
        }
    )

    assert result["sql_output"][0]["title"] == "Leave policy"
    assert "ORDER BY created_at DESC LIMIT 5" in db.calls[0][0]
