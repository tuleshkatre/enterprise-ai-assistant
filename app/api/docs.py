"""Enterprise presentation helpers for the generated API documentation."""

from html import escape

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": "User registration and JWT session lifecycle.",
    },
    {
        "name": "Documents",
        "description": "Tenant-isolated PDF upload, indexing, listing, and deletion.",
    },
    {
        "name": "RAG Chat",
        "description": "Direct document-grounded normal and streaming answers.",
    },
    {
        "name": "LangGraph Chat",
        "description": "Agent-routed document, web, SQL, calculator, and memory workflows.",
    },
    {
        "name": "Conversations",
        "description": "Conversation and message lifecycle management.",
    },
    {"name": "System", "description": "Operational health and readiness information."},
]

SWAGGER_PARAMETERS = {
    "defaultModelsExpandDepth": -1,
    "defaultModelExpandDepth": 2,
    "docExpansion": "none",
    "displayRequestDuration": True,
    "persistAuthorization": True,
    "tryItOutEnabled": True,
    "syntaxHighlight.theme": "monokai",
}

SWAGGER_CSS = """
<style>
  :root {
    color-scheme: light;
    --portal-navy: #102a43;
    --portal-blue: #175cd3;
    --portal-teal: #0f766e;
    --portal-border: #d9e2ec;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: #f5f7fb; }
  .portal-header {
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 64px;
    padding: 0 32px;
    color: #fff;
    background: linear-gradient(110deg, #102a43 0%, #163f67 68%, #0f766e 100%);
    box-shadow: 0 2px 10px rgba(16, 42, 67, .22);
  }
  .portal-brand { display: flex; align-items: center; gap: 12px; }
  .portal-mark {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border: 1px solid rgba(255,255,255,.35);
    border-radius: 9px;
    background: rgba(255,255,255,.12);
    font: 700 14px/1 system-ui, sans-serif;
  }
  .portal-name { font: 650 17px/1.2 system-ui, sans-serif; letter-spacing: .1px; }
  .portal-subtitle { margin-top: 3px; color: #bcccdc; font: 12px/1.2 system-ui, sans-serif; }
  .portal-meta { display: flex; align-items: center; gap: 8px; }
  .portal-badge {
    padding: 6px 10px;
    border: 1px solid rgba(255,255,255,.24);
    border-radius: 999px;
    background: rgba(255,255,255,.1);
    font: 600 11px/1 system-ui, sans-serif;
    text-transform: uppercase;
    letter-spacing: .45px;
  }
  .swagger-ui { color: #172033; }
  .swagger-ui .topbar { display: none; }
  .swagger-ui .wrapper { max-width: 1320px; padding: 0 28px; }
  .swagger-ui .information-container { padding: 30px 0 12px; }
  .swagger-ui .info { margin: 0; }
  .swagger-ui .info .title { color: var(--portal-navy); font-size: 34px; letter-spacing: -.5px; }
  .swagger-ui .info .title small { top: -4px; }
  .swagger-ui .info .description { max-width: 900px; color: #486581; }
  .swagger-ui .scheme-container {
    margin: 18px 0 24px;
    padding: 16px 0;
    background: transparent;
    border-top: 1px solid var(--portal-border);
    border-bottom: 1px solid var(--portal-border);
    box-shadow: none;
  }
  .swagger-ui .auth-wrapper { justify-content: flex-start; }
  .swagger-ui .btn.authorize { border-color: var(--portal-teal); color: var(--portal-teal); border-radius: 6px; }
  .swagger-ui .opblock-tag {
    margin: 0 0 10px;
    padding: 16px 12px;
    color: #243b53;
    border-bottom: 1px solid #bcccdc;
  }
  .swagger-ui .opblock { border-radius: 8px; box-shadow: 0 2px 8px rgba(16,42,67,.06); }
  .swagger-ui .models { display: none; }
  .portal-footer {
    max-width: 1320px;
    margin: 42px auto 0;
    padding: 22px 28px 30px;
    color: #627d98;
    border-top: 1px solid var(--portal-border);
    font: 12px/1.5 system-ui, sans-serif;
  }
  @media (max-width: 700px) {
    .portal-header { padding: 12px 18px; align-items: flex-start; gap: 14px; }
    .portal-subtitle { display: none; }
    .portal-meta { flex-direction: column; align-items: flex-end; }
    .swagger-ui .wrapper { padding: 0 14px; }
    .swagger-ui .info .title { font-size: 28px; }
  }
</style>
"""


def enterprise_swagger_ui(
    openapi_url: str,
    title: str,
    version: str,
    environment: str,
) -> HTMLResponse:
    safe_environment = escape(environment)
    safe_version = escape(version)
    generated = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=title,
        swagger_ui_parameters=SWAGGER_PARAMETERS,
    )
    header = f"""
    <header class="portal-header">
      <div class="portal-brand">
        <div class="portal-mark">AI</div>
        <div>
          <div class="portal-name">Enterprise AI Assistant</div>
          <div class="portal-subtitle">Internal API Developer Portal</div>
        </div>
      </div>
      <div class="portal-meta">
        <span class="portal-badge">{safe_environment}</span>
        <span class="portal-badge">v{safe_version}</span>
      </div>
    </header>
    """
    footer = """
    <footer class="portal-footer">
      Enterprise AI Assistant API · Authenticated, tenant-isolated access · OpenAPI 3.1
    </footer>
    """
    content = generated.body.decode("utf-8")
    content = content.replace("</head>", f"{SWAGGER_CSS}</head>")
    content = content.replace("<body>", f"<body>{header}")
    content = content.replace("</body>", f"{footer}</body>")
    return HTMLResponse(content=content)
