"""Authenticated command-line client for the Enterprise AI MCP server."""

import argparse
import asyncio
import json
import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

import httpx2
from dotenv import load_dotenv

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp/")


def _load_mcp_environment() -> None:
    load_dotenv(".env.mcp", override=False)


def mcp_access_token() -> str:
    _load_mcp_environment()
    token = os.getenv("MCP_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "Set MCP_ACCESS_TOKEN, or configure MCP_EMAIL and MCP_PASSWORD in .env.mcp"
        )
    return token


def _login_url() -> str:
    configured_url = os.getenv("MCP_LOGIN_URL")
    if configured_url:
        return configured_url
    parts = urlsplit(os.getenv("MCP_URL", MCP_URL))
    return urlunsplit((parts.scheme, parts.netloc, "/api/v1/login", "", ""))


async def resolve_access_token() -> str:
    """Return an explicit token or obtain a short-lived token automatically."""
    _load_mcp_environment()
    token = os.getenv("MCP_ACCESS_TOKEN")
    if token:
        return token

    email = os.getenv("MCP_EMAIL")
    password = os.getenv("MCP_PASSWORD")
    if not email or not password:
        raise RuntimeError(
            "Create .env.mcp with MCP_EMAIL and MCP_PASSWORD, or set MCP_ACCESS_TOKEN"
        )

    async with httpx2.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _login_url(),
            json={"email": email, "password": password},
        )
        response.raise_for_status()
        return response.json()["access_token"]


@asynccontextmanager
async def authenticated_client():
    token = await resolve_access_token()
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"}
    ) as http_client:
        async with streamable_http_client(MCP_URL, http_client=http_client) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as client:
                await client.initialize()
                yield client


async def list_tools():
    async with authenticated_client() as client:
        return (await client.list_tools()).tools


async def call_tool(tool_name: str, arguments: dict):
    async with authenticated_client() as client:
        return await client.call_tool(tool_name, arguments)


def print_tool_result(result) -> None:
    for item in result.content:
        if not hasattr(item, "text"):
            continue
        try:
            print(json.dumps(json.loads(item.text), indent=2))
        except json.JSONDecodeError:
            print(item.text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enterprise AI MCP Client")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List available MCP tools")

    search = subparsers.add_parser("search_documents")
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=5)

    knowledge = subparsers.add_parser("ask_knowledge_base")
    knowledge.add_argument("--question", required=True)

    analytics = subparsers.add_parser("run_safe_analytics")
    analytics.add_argument("--question", required=True)

    remember = subparsers.add_parser("remember_user_fact")
    remember.add_argument("--attribute", required=True)
    remember.add_argument("--value", required=True)

    forget = subparsers.add_parser("forget_user_fact")
    forget.add_argument("--attribute", required=True)

    subparsers.add_parser("system_diagnostics")
    return parser


async def main() -> None:
    args = build_parser().parse_args()
    if args.command == "list":
        for tool in await list_tools():
            print(f"- {tool.name}: {tool.description or ''}")
        return

    arguments = {
        key: value
        for key, value in vars(args).items()
        if key != "command" and value is not None
    }
    print_tool_result(await call_tool(args.command, arguments))


if __name__ == "__main__":
    asyncio.run(main())
