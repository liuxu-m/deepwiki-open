"""Unit tests for api/mcp/tools.py MCP tool implementations."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

# Make the project root importable so 'from api.mcp.tools import ...' resolves
# to the api/ package directory (not api.py at the project root).
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from api.mcp.tools import (
    MCPError,
    ERR_BACKEND_UNAVAILABLE,
    ERR_PROJECT_NOT_FOUND,
    ERR_WIKI_NOT_GENERATED,
    ERR_PAGE_NOT_FOUND,
    _parse_repo_url,
    list_processed_projects,
    get_wiki_structure,
    query_wiki_content,
)


# ---------------------------------------------------------------------------
# _parse_repo_url — synchronous helper
# ---------------------------------------------------------------------------

class TestParseRepoUrl:
    def test_github_https(self):
        owner, repo, repo_type = _parse_repo_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        assert repo_type == "github"

    def test_github_https_with_git_suffix(self):
        owner, repo, repo_type = _parse_repo_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
        assert repo_type == "github"

    def test_gitlab_https(self):
        owner, repo, repo_type = _parse_repo_url("https://gitlab.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        assert repo_type == "gitlab"

    def test_gitlab_https_with_git_suffix(self):
        owner, repo, repo_type = _parse_repo_url("https://gitlab.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
        assert repo_type == "gitlab"

    def test_github_colon_prefix(self):
        owner, repo, repo_type = _parse_repo_url("github:owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        assert repo_type == "github"

    def test_gitlab_colon_prefix(self):
        owner, repo, repo_type = _parse_repo_url("gitlab:owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        assert repo_type == "gitlab"

    def test_deeply_nested_repo(self):
        """Owner/repo where repo name contains slashes."""
        owner, repo, repo_type = _parse_repo_url("https://github.com/owner/sub/repo")
        assert owner == "owner"
        assert repo == "sub/repo"
        assert repo_type == "github"

    def test_invalid_url_raises_mcp_error(self):
        exc = pytest.raises(MCPError, _parse_repo_url, "not-a-url")
        assert exc.value.code == ERR_PROJECT_NOT_FOUND

    def test_empty_string_raises_mcp_error(self):
        exc = pytest.raises(MCPError, _parse_repo_url, "")
        assert exc.value.code == ERR_PROJECT_NOT_FOUND

    def test_owner_only_raises_mcp_error(self):
        exc = pytest.raises(MCPError, _parse_repo_url, "https://github.com/owner")
        assert exc.value.code == ERR_PROJECT_NOT_FOUND


# ---------------------------------------------------------------------------
# list_processed_projects — async tool
# ---------------------------------------------------------------------------
# pytest-asyncio is not installed in this environment; async test functions
# are wrapped with asyncio.run() so they execute as regular pytest tests.
# @pytest.mark.asyncio is kept as documentation of the async nature.

@pytest.mark.asyncio
async def test_list_processed_projects_backend_unavailable():
    """Health check fails → MCPError(-1)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = False

        with pytest.raises(MCPError) as exc_info:
            await list_processed_projects(mock_client)

        assert exc_info.value.code == ERR_BACKEND_UNAVAILABLE

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_list_processed_projects_success():
    """Health check passes → returns project list."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner1", "repo": "repo1", "language": "en"},
            {"owner": "owner2", "repo": "repo2", "language": "zh"},
        ]

        result = await list_processed_projects(mock_client)

        assert len(result) == 2
        mock_client.list_processed_projects.assert_awaited_once_with(language=None)

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_list_processed_projects_with_language_filter():
    """Language filter is applied client-side when backend returns all projects."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner1", "repo": "repo1", "language": "en"},
            {"owner": "owner2", "repo": "repo2", "language": "zh"},
        ]

        result = await list_processed_projects(mock_client, language="zh")

        assert len(result) == 1
        assert result[0]["repo"] == "repo2"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# get_wiki_structure — async tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_wiki_structure_backend_unavailable():
    """Health check fails → MCPError(-1)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = False

        with pytest.raises(MCPError) as exc_info:
            await get_wiki_structure(mock_client, "https://github.com/owner/repo")

        assert exc_info.value.code == ERR_BACKEND_UNAVAILABLE

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_get_wiki_structure_project_not_found():
    """Project not in processed list → MCPError(-2)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "other", "repo": "other", "language": "en"},
        ]

        with pytest.raises(MCPError) as exc_info:
            await get_wiki_structure(mock_client, "https://github.com/owner/repo")

        assert exc_info.value.code == ERR_PROJECT_NOT_FOUND

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_get_wiki_structure_not_generated():
    """Project in list but wiki cache is None → MCPError(-3)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner", "repo": "repo", "language": "en"},
        ]
        mock_client.get_wiki_cache.return_value = None

        with pytest.raises(MCPError) as exc_info:
            await get_wiki_structure(mock_client, "https://github.com/owner/repo")

        assert exc_info.value.code == ERR_WIKI_NOT_GENERATED

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_get_wiki_structure_wiki_structure_is_none():
    """Project in list but wiki_structure key is None → MCPError(-3)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner", "repo": "repo", "language": "en"},
        ]
        mock_client.get_wiki_cache.return_value = {
            "wiki_structure": None,
            "generated_pages": {},
        }

        with pytest.raises(MCPError) as exc_info:
            await get_wiki_structure(mock_client, "https://github.com/owner/repo")

        assert exc_info.value.code == ERR_WIKI_NOT_GENERATED

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_get_wiki_structure_success():
    """Valid project with cache → returns wiki_structure dict."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner", "repo": "repo", "language": "en"},
        ]
        wiki_structure = {
            "title": "Test Wiki",
            "pages": [{"id": "p1", "title": "Overview"}],
            "sections": [],
        }
        mock_client.get_wiki_cache.return_value = {
            "wiki_structure": wiki_structure,
            "generated_pages": {},
        }

        result = await get_wiki_structure(mock_client, "https://github.com/owner/repo")

        assert result == wiki_structure
        mock_client.get_wiki_cache.assert_awaited_once_with(
            "owner", "repo", "github", "en"
        )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# query_wiki_content — async tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_wiki_content_backend_unavailable():
    """Health check fails → MCPError(-1)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = False

        with pytest.raises(MCPError) as exc_info:
            await query_wiki_content(mock_client, "https://github.com/owner/repo")

        assert exc_info.value.code == ERR_BACKEND_UNAVAILABLE

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_query_wiki_content_project_not_found():
    """Project not in processed list → MCPError(-2)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = []

        with pytest.raises(MCPError) as exc_info:
            await query_wiki_content(mock_client, "https://github.com/owner/repo")

        assert exc_info.value.code == ERR_PROJECT_NOT_FOUND

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_query_wiki_content_wiki_not_generated():
    """Wiki cache is None → MCPError(-3)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner", "repo": "repo", "language": "en"},
        ]
        mock_client.get_wiki_cache.return_value = None

        with pytest.raises(MCPError) as exc_info:
            await query_wiki_content(mock_client, "https://github.com/owner/repo")

        assert exc_info.value.code == ERR_WIKI_NOT_GENERATED

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_query_wiki_content_page_not_found():
    """page_id provided but not in generated_pages → MCPError(-4)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner", "repo": "repo", "language": "en"},
        ]
        mock_client.get_wiki_cache.return_value = {
            "wiki_structure": {},
            "generated_pages": {
                "page-1": {"id": "page-1", "title": "Page 1", "content": "# Hello"},
            },
        }

        with pytest.raises(MCPError) as exc_info:
            await query_wiki_content(
                mock_client, "https://github.com/owner/repo", page_id="nonexistent"
            )

        assert exc_info.value.code == ERR_PAGE_NOT_FOUND

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_query_wiki_content_no_page_id_returns_all_pages():
    """page_id omitted → returns list of all pages (up to 10)."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner", "repo": "repo", "language": "en"},
        ]
        generated_pages = {
            f"page-{i}": {"id": f"page-{i}", "title": f"Page {i}", "content": f"# {i}"}
            for i in range(15)  # more than 10
        }
        mock_client.get_wiki_cache.return_value = {
            "wiki_structure": {},
            "generated_pages": generated_pages,
        }

        result = await query_wiki_content(mock_client, "https://github.com/owner/repo")

        assert isinstance(result, list)
        assert len(result) == 10  # capped at 10

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_query_wiki_content_page_id_returns_single_page():
    """page_id provided and found → returns that page dict."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_processed_projects.return_value = [
            {"owner": "owner", "repo": "repo", "language": "en"},
        ]
        mock_client.get_wiki_cache.return_value = {
            "wiki_structure": {},
            "generated_pages": {
                "page-1": {"id": "page-1", "title": "Overview", "content": "# Overview"},
                "page-2": {"id": "page-2", "title": "API", "content": "# API"},
            },
        }

        result = await query_wiki_content(
            mock_client, "https://github.com/owner/repo", page_id="page-2"
        )

        assert isinstance(result, dict)
        assert result["id"] == "page-2"
        assert result["title"] == "API"

    asyncio.run(_run())
