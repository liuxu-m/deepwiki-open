# DeepWiki 查询 Skill

通过 DeepWiki 现有 HTTP 接口，为 Claude Code 提供对已生成 Wiki 文档的只读查询能力。

## 配置

使用前请先设置 `DEEPWIKI_BASE_URL`。

示例：

```bash
export DEEPWIKI_BASE_URL="http://127.0.0.1:8001"
```

Windows：

```bash
set DEEPWIKI_BASE_URL=http://127.0.0.1:8001
```

## 命令

### `/deepwiki-projects [language]`
列出 DeepWiki 中已经处理过的项目，方便先确认有哪些仓库可查询。

示例：

```bash
node skills/deepwiki-query/scripts/deepwiki-projects.js
node skills/deepwiki-query/scripts/deepwiki-projects.js zh
```

### `/deepwiki <repo_url> [language]`
查看某个已处理项目的 Wiki 结构总览。

示例：

```bash
node skills/deepwiki-query/scripts/deepwiki.js https://github.com/owner/repo
node skills/deepwiki-query/scripts/deepwiki.js github:owner/repo zh
```

### `/deepwiki-page <repo_url> <page_id> [language]`
查看指定 Wiki 页面对应的 Markdown 内容。

示例：

```bash
node skills/deepwiki-query/scripts/deepwiki-page.js https://github.com/owner/repo architecture-overview
```

### `/deepwiki-chat <repo_url> [language]`
输出适合继续追问的项目导览内容，用于后续对话。

示例：

```bash
node skills/deepwiki-query/scripts/deepwiki-chat.js https://github.com/owner/repo
```

## 后端要求

目标仓库必须已经在 DeepWiki 中生成过 Wiki 数据。

后端需要提供以下接口：
- `GET /api/processed_projects`
- `GET /api/wiki_cache`

## 部署说明

### 本地后端
将 `DEEPWIKI_BASE_URL` 指向本地 DeepWiki 后端即可。

### 服务器后端
将 `DEEPWIKI_BASE_URL` 指向 Claude Code 所在机器或 VPN 环境可以访问到的已部署 DeepWiki HTTP 服务。

本 skill 有意替代基于 MCP 的集成方式，以避免 MCP 运行时和依赖冲突问题。
