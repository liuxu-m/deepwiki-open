"""MCP Server entrypoint - stdio transport with JSON-RPC 2.0."""
import asyncio
import json
import sys
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from api.mcp.client import DeepWikiClient
from api.mcp import tools as mcp_tools


# Server name
APP_NAME = "deepwiki-mcp"
server = Server(APP_NAME)

# Global client instance (reused across tool calls, not recreated per call)
_client: Optional[DeepWikiClient] = None


def get_client() -> DeepWikiClient:
    global _client
    if _client is None:
        _client = DeepWikiClient()
    return _client


# ── Tool Definitions ──────────────────────────────────────────────────────────

TOOL_LIST_PROJECTS = Tool(
    name="list_processed_projects",
    description="List all DeepWiki-processed projects. Returns owner, repo, language, summary, and note for each project.",
    inputSchema={
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "Filter by language (e.g., 'zh', 'en', 'ja')",
            }
        },
    },
)

TOOL_GET_STRUCTURE = Tool(
    name="get_wiki_structure",
    description="Get the wiki structure (pages + sections) for a specific project. Returns page titles, importance, related files, and section organization.",
    inputSchema={
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": "GitHub/GitLab URL of the repository (e.g., https://github.com/owner/repo)",
            },
            "language": {
                "type": "string",
                "description": "Language code (e.g., 'en', 'zh'). Defaults to 'en'.",
            },
        },
        "required": ["repo_url"],
    },
)

TOOL_QUERY_CONTENT = Tool(
    name="query_wiki_content",
    description="Get the Markdown content of one or all wiki pages for a project. Use to retrieve the actual documentation text.",
    inputSchema={
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": "GitHub/GitLab URL of the repository",
            },
            "page_id": {
                "type": "string",
                "description": "Page ID to retrieve. If omitted, returns content for all pages (up to 10).",
            },
            "language": {
                "type": "string",
                "description": "Language code (e.g., 'en', 'zh'). Defaults to 'en'.",
            },
        },
        "required": ["repo_url"],
    },
)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [TOOL_LIST_PROJECTS, TOOL_GET_STRUCTURE, TOOL_QUERY_CONTENT]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls from Claude Code."""
    client = get_client()
    try:
        result: dict | list

        if name == "list_processed_projects":
            result = await mcp_tools.list_processed_projects(
                client, language=arguments.get("language")
            )

        elif name == "get_wiki_structure":
            result = await mcp_tools.get_wiki_structure(
                client,
                repo_url=arguments["repo_url"],
                language=arguments.get("language", "en"),
            )

        elif name == "query_wiki_content":
            result = await mcp_tools.query_wiki_content(
                client,
                repo_url=arguments["repo_url"],
                page_id=arguments.get("page_id"),
                language=arguments.get("language", "en"),
            )

        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    except mcp_tools.MCPError as e:
        return [TextContent(type="text", text=json.dumps(e.to_dict(), ensure_ascii=False))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(e), "code": mcp_tools.ERR_BACKEND_UNAVAILABLE}, ensure_ascii=False),
            )
        ]
    # Do NOT close client after every call; reuse the global singleton


def run():
    """Entry point for `python -m api.mcp` or direct execution."""
    asyncio.run(_main())


async def _main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
