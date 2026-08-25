import pytest

from app.agents.supervisor_agent import supervisor_agent


@pytest.mark.parametrize(
    "query",
    [
        "How many conversations do I have?",
        "How many documents have I uploaded?",
        "Count messages by role",
        "Show document chunks in the database",
    ],
)
def test_supervisor_routes_database_analytics_to_sql(query):
    assert supervisor_agent({"query": query}) == {"route": "sql"}


def test_supervisor_preserves_existing_routes():
    assert supervisor_agent({"query": "2 + 3"}) == {"route": "calculator"}
    assert supervisor_agent({"query": "latest stock market news"}) == {"route": "web"}
    assert supervisor_agent({"query": "How many sick leaves are allowed?"}) == {
        "route": "document"
    }


def test_supervisor_does_not_route_unsupported_business_tables_to_sql():
    assert supervisor_agent({"query": "Group employees by department"}) == {
        "route": "document"
    }
