# DeepWiki Query Skill

Provides read-only access to DeepWiki-generated documentation through existing DeepWiki HTTP APIs.

## Configuration

Set `DEEPWIKI_BASE_URL` before using this skill.

Examples:

```bash
export DEEPWIKI_BASE_URL="http://127.0.0.1:8001"
```

Windows:

```bash
set DEEPWIKI_BASE_URL=http://127.0.0.1:8001
```

## Commands

### `/deepwiki <repo_url> [language]`
Show wiki structure overview for a processed project.

Examples:

```bash
node .claude/skills/deepwiki-query/scripts/deepwiki.js https://github.com/owner/repo
node .claude/skills/deepwiki-query/scripts/deepwiki.js github:owner/repo zh
```

### `/deepwiki-page <repo_url> <page_id> [language]`
Show one wiki page as markdown.

Examples:

```bash
node .claude/skills/deepwiki-query/scripts/deepwiki-page.js https://github.com/owner/repo architecture-overview
```

### `/deepwiki-chat <repo_url> [language]`
Bootstrap a guided project overview for follow-up chat.

Examples:

```bash
node .claude/skills/deepwiki-query/scripts/deepwiki-chat.js https://github.com/owner/repo
```

## Backend Requirements

The target project must already have generated wiki data in DeepWiki.

Required backend endpoints:
- `GET /api/processed_projects`
- `GET /api/wiki_cache`

## Deployment Notes

### Local backend
Point `DEEPWIKI_BASE_URL` to a local DeepWiki backend.

### Server backend
Point `DEEPWIKI_BASE_URL` to the deployed DeepWiki HTTP service reachable from the Claude Code machine or VPN environment.

This skill intentionally replaces the MCP-based integration to avoid MCP runtime and dependency conflicts.
