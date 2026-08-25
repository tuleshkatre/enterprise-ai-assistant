from langgraph.graph import END, StateGraph

from app.agents.agent_state import AgentState
from app.agents.calculator_agent import calculator_agent
from app.agents.context_resolver_agent import context_resolver_agent
from app.agents.conversation_agent import conversation_agent
from app.agents.document_agent import document_agent
from app.agents.memory_agent import memory_agent
from app.agents.response_agent import response_agent
from app.agents.response_stream_agent import response_stream_agent
from app.agents.retrieve_agent import retrieve_agent
from app.agents.rewrite_agent import rewrite_agent
from app.agents.sql_agent import sql_agent
from app.agents.supervisor_agent import supervisor_agent
from app.agents.web_agent import web_agent

builder = StateGraph(AgentState)

# Nodes

builder.add_node("context_resolver", context_resolver_agent)

builder.add_node("supervisor", supervisor_agent)

builder.add_node("document", document_agent)

builder.add_node("rewrite", rewrite_agent)

builder.add_node("retrieve", retrieve_agent)

builder.add_node("web", web_agent)

builder.add_node("calculator", calculator_agent)

builder.add_node("sql", sql_agent)

builder.add_node("conversation", conversation_agent)

builder.add_node("memory", memory_agent)

builder.add_node("response", response_agent)

# Entry

builder.set_entry_point("context_resolver")

builder.add_edge("context_resolver", "supervisor")

# Routing

builder.add_conditional_edges(
    "supervisor",
    lambda state: state["route"],
    {
        "document": "document",
        "web": "web",
        "calculator": "calculator",
        "sql": "sql",
        "conversation": "conversation",
        "memory": "memory",
    },
)

# Document Flow

builder.add_edge("document", "rewrite")

builder.add_edge("rewrite", "retrieve")

builder.add_edge("retrieve", "response")

# Other Agents

builder.add_edge("web", "response")

builder.add_edge("calculator", "response")

builder.add_edge("sql", "response")

builder.add_edge("conversation", "response")

builder.add_edge("memory", "response")

# Finish

builder.add_edge("response", END)

graph = builder.compile()


# New Stream Graph For Streaming Responses

# ==================================================
# STREAM GRAPH
# ==================================================

stream_builder = StateGraph(AgentState)

stream_builder.add_node("context_resolver", context_resolver_agent)

stream_builder.add_node("supervisor", supervisor_agent)

stream_builder.add_node("document", document_agent)

stream_builder.add_node("rewrite", rewrite_agent)

stream_builder.add_node("retrieve", retrieve_agent)

stream_builder.add_node("web", web_agent)

stream_builder.add_node("calculator", calculator_agent)

stream_builder.add_node("sql", sql_agent)

stream_builder.add_node("conversation", conversation_agent)

stream_builder.add_node("memory", memory_agent)

stream_builder.add_node("response_stream", response_stream_agent)

stream_builder.set_entry_point("context_resolver")

stream_builder.add_edge("context_resolver", "supervisor")

stream_builder.add_conditional_edges(
    "supervisor",
    lambda state: state["route"],
    {
        "document": "document",
        "web": "web",
        "calculator": "calculator",
        "sql": "sql",
        "conversation": "conversation",
        "memory": "memory",
    },
)

stream_builder.add_edge("document", "rewrite")

stream_builder.add_edge("rewrite", "retrieve")

stream_builder.add_edge("retrieve", "response_stream")

stream_builder.add_edge("web", "response_stream")

stream_builder.add_edge("calculator", "response_stream")

stream_builder.add_edge("sql", "response_stream")

stream_builder.add_edge("conversation", "response_stream")

stream_builder.add_edge("memory", "response_stream")

stream_builder.add_edge("response_stream", END)

stream_graph = stream_builder.compile()
