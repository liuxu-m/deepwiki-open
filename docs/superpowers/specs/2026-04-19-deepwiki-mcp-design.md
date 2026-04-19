---
name: deepwiki-mcp-design
description: DeepWiki MCP Server design - query-only tools exposing wiki data to Claude Code
type: reference
---

# DeepWiki MCP Server Design

## Overview

Expose DeepWiki's generated wiki data to Claude Code via the MCP (Model Context Protocol) stdio interface, enabling Claude Code to query existing project documentation without accessing the web UI.

## Architecture

```
Claude Code
    ↕ stdio (JSON-RPC 2.0)
MCP Server (Python, new process)
    ↕ HTTP
DeepWiki Backend (http://localhost:8001)
    ↕
SQLite (processed_projects.json) + Wiki Cache (JSON files)
```

- MCP Server is an independent Python process communicating with Claude Code via stdio JSON-RPC 2.0
- It calls DeepWiki backend REST APIs over HTTP (read-only)
- Only reads already-processed projects; no task creation or mutation

## Constraints

- **Query-only**: No task creation, pause, resume, delete, or refresh triggers
- **Existing projects only**: New projects must be generated via the Web UI first
- **Backend required**: MCP Server depends on the running DeepWiki backend
- **No RAG exposure**: The RAG pipeline is not exposed via MCP (only pre-generated wiki JSON)

## MCP Tools

### `list_processed_projects`

List all processed projects.

**Arguments:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `language` | `string` | No | Filter by language (e.g., `"zh"`, `"en"`) |

**Returns:** `ProcessedProjectEntry[]`

### `get_wiki_structure`

Get the wiki structure (pages + sections) for a project.

**Arguments:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `repo_url` | `string` | Yes | GitHub/GitLab URL of the repository |

**Returns:** `WikiStructureModel`

```typescript
WikiStructureModel {
  id: string
  title: string
  description: string
  pages: WikiPage[]
  sections: WikiSection[] | null
}

WikiPage {
  id: string
  title: string
  content: string        // Markdown content (populated on demand)
  filePaths: string[]   // Related source files
  importance: string     // "high" | "medium" | "low"
  relatedPages: string[] // IDs of related pages
}

WikiSection {
  id: string
  title: string
  pages: string[]        // Page IDs in this section
  subsections: string[] | null
}
```

### `query_wiki_content`

Get the full Markdown content of a specific wiki page.

**Arguments:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `repo_url` | `string` | Yes | GitHub/GitLab URL of the repository |
| `page_id` | `string` | No | Page ID. If omitted, returns content for all pages (up to 10) |

**Returns:** `WikiPage | WikiPage[]`

## Error Responses

| Scenario | Response |
|----------|----------|
| Backend unavailable | `{"error": "Backend unavailable", "code": -1}` |
| Project not processed | `{"error": "Project not found in processed projects", "code": -2}` |
| Wiki not generated | `{"error": "Wiki not generated yet. Generate it via Web UI first.", "code": -3}` |
| Page not found | `{"error": "Page not found", "code": -4}` |

## Data Reuse

| Component | Source | Reused As |
|-----------|--------|-----------|
| `ProcessedProjectEntry` | `api/api.py:61` | Direct model reuse |
| `WikiStructureModel` | `api/api.py:91` | Direct model reuse |
| `WikiPage` | `api/api.py:50` | Direct model reuse |
| `WikiSection` | `api/api.py:81` | Direct model reuse |
| Project list API | `GET /wiki/projects` | Backend HTTP call |
| Wiki structure API | `GET /wiki/structure?repo_url=...` | Backend HTTP call |
| Wiki cache API | `GET /wiki/cache?repo_url=...&path=...` | Backend HTTP call |

## Implementation Notes

- MCP Server uses `mcp.server.fastmcp` or raw `stdio` JSON-RPC 2.0
- Reuses Pydantic models from `api/api.py` for type safety
- HTTP client: `httpx` (async, already available in backend deps)
- Backend URL configurable via `DEEPWIKI_MCP_BACKEND_URL` env var (default: `http://localhost:8001`)
- Graceful degradation: if backend is unreachable, return clear error instead of crashing

## File Structure

```
api/mcp/
  __init__.py
  server.py          # MCP Server entrypoint (stdio mode)
  tools.py           # Tool definitions
  client.py          # Backend HTTP client wrapper
  models.py          # Pydantic models (re-exported from api.api)
```

## Testing Strategy

- Unit tests for each tool handler (mock HTTP responses)
- Integration tests: start backend + MCP server, verify JSON-RPC round-trip
- Test error cases: backend down, project not found, page not found
