from app.agents.supervisor_agent import supervisor_agent


def test_employee_policy_count_question_routes_to_documents():
    result = supervisor_agent(
        {
            "query": "How many annual paid leave days do employees receive?",
            "context_route": None,
        }
    )

    assert result == {"route": "document"}


def test_supported_database_count_still_routes_to_sql():
    result = supervisor_agent(
        {
            "query": "How many documents have I uploaded?",
            "context_route": None,
        }
    )

    assert result == {"route": "sql"}
