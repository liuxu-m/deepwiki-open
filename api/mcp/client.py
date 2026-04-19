"""Async HTTP client for DeepWiki backend communication."""
import os
from typing import Optional

import httpx

BASE_URL = os.environ.get("DEEPWIKI_MCP_BACKEND_URL", "http://localhost:8001")
TIMEOUT = 30.0


class DeepWikiClient:
    """Client for DeepWiki backend read-only APIs."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=TIMEOUT)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def list_processed_projects(
        self, language: Optional[str] = None
    ) -> list[dict]:
        """
        GET /api/processed_projects

        Returns all processed project entries.
        Optionally filter by language (client-side filtering when backend
        does not support server-side language filtering).
        """
        client = await self._get_client()
        params = {"language": language} if language else {}
        response = await client.get(f"{self.base_url}/api/processed_projects", params=params)
        response.raise_for_status()
        return response.json()

    async def get_wiki_cache(
        self, owner: str, repo: str, repo_type: str, language: str = "en"
    ) -> Optional[dict]:
        """
        GET /api/wiki_cache

        Returns full WikiCacheData (wiki_structure + generated_pages).
        Returns None if cache is not found (backend returns 200 with null body).
        """
        client = await self._get_client()
        params = {
            "owner": owner,
            "repo": repo,
            "repo_type": repo_type,
            "language": language,
        }
        response = await client.get(f"{self.base_url}/api/wiki_cache", params=params)
        # Backend returns 200 with null/None body when cache is missing, not 404
        if response.status_code == 200 and response.text in ("null", ""):
            return None
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """Check if backend is reachable."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
