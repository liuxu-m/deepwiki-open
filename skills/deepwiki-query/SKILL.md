---
name: deepwiki-query
description: Use when the user wants to check what projects DeepWiki has indexed, browse a repo's wiki structure, read a specific wiki page, create a new wiki generation task, or get a project overview for chat context — and a DeepWiki backend is running (local or remote). Symptoms: user asks "what wikis are available", "show me the wiki for X repo", "generate a wiki for Y repo", "what pages does the wiki have", or references deepwiki in any form.
---

# DeepWiki 查询

通过 DeepWiki HTTP 后端查询 Wiki 文档和创建生成任务。默认连接 `http://dreamxu.xyz:8001`，可通过 `DEEPWIKI_BASE_URL` 覆盖。

## 命令速查

脚本位于 `skills/deepwiki-query/scripts/`，详细参数见 `--help`。`repo_url` 支持 `https://github.com/owner/repo`、`github:owner/repo`、`owner/repo`。

| 脚本 | 用途 | 典型调用 |
|---|---|---|
| `deepwiki-projects.js` | 列出已索引项目 | `node ...projects.js [lang]` |
| `deepwiki.js` | Wiki 结构总览 | `node ...deepwiki.js <repo> [lang]` |
| `deepwiki-page.js` | 单个页面内容 | `node ...deepwiki-page.js <repo> <page_id> [lang]` |
| `deepwiki-chat.js` | 对话导览摘要 | `node ...deepwiki-chat.js <repo> [lang]` |
| `deepwiki-create-task.js` | 创建生成任务 | `node ...create-task.js <repo> [lang] [provider] [model]` |

## 推荐流程

1. 未知项目 → `deepwiki-projects.js`
2. 未知页面 → `deepwiki.js` 获取 page_id 列表
3. 已知 page_id → `deepwiki-page.js` 读内容
4. 对话准备 → `deepwiki-chat.js`
5. 新仓库 → `deepwiki-create-task.js` 提交任务

**读取页面前必须先查结构获取 page_id，禁止猜测。**

## When to Use

- 用户询问 DeepWiki 收录了什么、某仓库 Wiki 结构、某页面内容、对话上下文、创建新任务
- **When NOT to use**: 无后端运行；用户要修改已生成 Wiki 内容（需 Web UI）

## 常见问题

| 错误 | 原因/解决 |
|---|---|
| `无法连接到 DeepWiki 后端` | `DEEPWIKI_BASE_URL` 未设置或后端未启动 |
| `Wiki 尚未生成` | 先创建任务或 Web UI 生成 |
| `页面不存在: xxx` | 错误输出列出所有可用 page_id，从中选取 |
| 远程不可达 | 确认 8001 端口开放 |
