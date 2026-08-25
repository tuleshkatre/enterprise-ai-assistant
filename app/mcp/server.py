import sys
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.config import settings
from app.mcp.auth import JWTTokenVerifier
from app.mcp.tools.analytics import run_safe_analytics
from app.mcp.tools.diagnostics import system_diagnostics
from app.mcp.tools.document_search import search_documents
from app.mcp.tools.knowledge_base import ask_knowledge_base
from app.mcp.tools.memories import forget_user_fact, remember_user_fact

mcp = MCPServer(
    "EnterpriseAI",
    auth=AuthSettings(
        issuer_url=settings.mcp_issuer_url,
        resource_server_url=settings.mcp_resource_server_url,
        required_scopes=["mcp:read"],
    ),
    token_verifier=JWTTokenVerifier(),
)


mcp.tool()(search_documents)
mcp.tool()(ask_knowledge_base)
mcp.tool()(run_safe_analytics)
mcp.tool()(remember_user_fact)
mcp.tool()(forget_user_fact)
mcp.tool()(system_diagnostics)


if __name__ == "__main__":
    mcp.run()
