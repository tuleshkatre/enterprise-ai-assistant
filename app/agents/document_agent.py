from app.observability.langsmith import add_trace_metadata


def document_agent(state):

    print("DOCUMENT AGENT RUNNING")

    add_trace_metadata(route="document")
    return {"observability": {"document_route_started": True}}
