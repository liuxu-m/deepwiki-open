"""MCP tool definitions and handlers."""
from __future__ import annotations

from typing import Any, Optional

from api.mcp.client import DeepWikiClient


class MCPError(Exception):
    """MCP tool error with code."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"error": self.message, "code": self.code}


# Error codes
ERR_BACKEND_UNAVAILABLE = -1
ERR_PROJECT_NOT_FOUND = -2
ERR_WIKI_NOT_GENERATED = -3
ERR_PAGE_NOT_FOUND = -4


def _parse_repo_url(repo_url: str) -> tuple[str, str, str]:
    """
    Parse repo_url into (owner, repo, repo_type).
    Supports: https://github.com/owner/repo, github:owner/repo,
              https://gitlab.com/owner/repo, gitlab:owner/repo,
              and URLs with .git suffix.
    """
    repo_url = repo_url.strip()

    # Detect repo_type and strip prefix
    repo_type = "github"  # default
    if "gitlab" in repo_url:
        repo_type = "gitlab"
        for prefix in ("https://gitlab.com/", "http://gitlab.com/", "gitlab:"):
            if repo_url.startswith(prefix):
                repo_url = repo_url[len(prefix):]
                break
    elif "github" in repo_url or repo_url.startswith("github:"):
        repo_type = "github"
        for prefix in ("https://github.com/", "http://github.com/", "github:"):
            if repo_url.startswith(prefix):
                repo_url = repo_url[len(prefix):]
                break
    else:
        # Unknown URL format, try common prefixes anyway
        for prefix in (
            "https://github.com/", "http://github.com/", "github:",
            "https://gitlab.com/", "http://gitlab.com/", "gitlab:",
        ):
            if repo_url.startswith(prefix):
                repo_url = repo_url[len(prefix):]
                break

    # Strip .git suffix
    repo_url = repo_url.rstrip("/").removesuffix(".git")

    parts = repo_url.split("/")
    if len(parts) < 2:
        raise MCPError("Invalid repo_url format", ERR_PROJECT_NOT_FOUND)

    owner = parts[0]
    repo = "/".join(parts[1:])  # repo name may contain /
    return owner, repo, repo_type


async def list_processed_projects(
    client: DeepWikiClient, language: Optional[str] = None
) -> list[dict]:
    """
    MCP tool: list_processed_projects
    Returns ProcessedProjectEntry[] from backend.
    """
    # Health check
    if not await client.health_check():
        raise MCPError("Backend unavailable", ERR_BACKEND_UNAVAILABLE)

    projects = await client.list_processed_projects(language=language)

    # Client-side language filter (backend does not support server-side filtering)
    if language:
        projects = [p for p in projects if p.get("language") == language]

    return projects


async def get_wiki_structure(
    client: DeepWikiClient, repo_url: str, language: str = "en"
) -> dict:
    """
    MCP tool: get_wiki_structure
    Returns WikiStructureModel (pages + sections) from wiki cache.
    """
    if not await client.health_check():
        raise MCPError("Backend unavailable", ERR_BACKEND_UNAVAILABLE)

    owner, repo, repo_type = _parse_repo_url(repo_url)

    # Verify project exists in processed list
    projects = await client.list_processed_projects()
    matching = [p for p in projects if p["owner"] == owner and p["repo"] == repo]
    if not matching:
        raise MCPError("Project not found in processed projects", ERR_PROJECT_NOT_FOUND)

    cache = await client.get_wiki_cache(owner, repo, repo_type, language)
    if cache is None:
        raise MCPError(
            "Wiki not generated yet. Generate it via Web UI first.",
            ERR_WIKI_NOT_GENERATED,
        )

    wiki_structure = cache.get("wiki_structure")
    if wiki_structure is None:
        raise MCPError(
            "Wiki not generated yet. Generate it via Web UI first.",
            ERR_WIKI_NOT_GENERATED,
        )

    return wiki_structure


async def query_wiki_content(
    client: DeepWikiClient,
    repo_url: str,
    page_id: Optional[str] = None,
    language: str = "en",
) -> dict | list[dict]:
    """
    MCP tool: query_wiki_content
    Returns WikiPage.content (Markdown) from wiki cache.
    If page_id is omitted, returns content for all pages (up to 10).
    """
    if not await client.health_check():
        raise MCPError("Backend unavailable", ERR_BACKEND_UNAVAILABLE)

    owner, repo, repo_type = _parse_repo_url(repo_url)

    # Verify project exists
    projects = await client.list_processed_projects()
    matching = [p for p in projects if p["owner"] == owner and p["repo"] == repo]
    if not matching:
        raise MCPError("Project not found in processed projects", ERR_PROJECT_NOT_FOUND)

    cache = await client.get_wiki_cache(owner, repo, repo_type, language)
    if cache is None:
        raise MCPError(
            "Wiki not generated yet. Generate it via Web UI first.",
            ERR_WIKI_NOT_GENERATED,
        )

    generated_pages: dict = cache.get("generated_pages", {})

    if page_id:
        page_data = generated_pages.get(page_id)
        if page_data is None:
            raise MCPError("Page not found", ERR_PAGE_NOT_FOUND)
        return page_data

    # Return all pages (up to 10)
    pages = list(generated_pages.values())[:10]
    return pages
