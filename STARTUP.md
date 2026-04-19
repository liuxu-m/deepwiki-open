# 启动步骤

## 后端启动

1. 激活 conda 环境
   ```bash
   conda activate D:\my_code\python_code\deepwiki-open\conda_envs\deepwiki-open
   ```

2. 进入项目目录
   ```bash
   cd D:\my_code\python_code\deepwiki-open
   ```

3. 启动后端
   ```bash
   python -m api.main
   ```

后端地址：`http://localhost:8001`

---

## 前端启动

### 开发模式

```bash
npm run dev
```

前端地址：`http://localhost:3000`

### 生产模式（推荐长期使用）

```bash
npm run build && npm start
npm start
set PORT=3005&& npm start
```

> 注意：每次修改代码后需要重新 `npm run build`

---

## Claude Code Skill 调用（推荐）

推荐使用 Claude Code skill 方式查询 DeepWiki 文档，而不是 MCP。

### 适用场景

Claude Code skill 是 **只读查询方式**，用于让 Claude Code 查询 DeepWiki 已生成的项目文档，不负责创建任务或触发文档生成。

因此启动顺序是：
1. 先启动 DeepWiki 后端
2. 确保目标项目已经在 DeepWiki 中生成过 Wiki
3. 再通过 Claude Code skill 查询该后端

### 环境变量

如果后端不是本机默认地址 `http://127.0.0.1:8001`，需要先设置环境变量：

```bash
export DEEPWIKI_BASE_URL="http://127.0.0.1:8001"
```

Windows 下可以使用：

```bash
set DEEPWIKI_BASE_URL=http://127.0.0.1:8001
```

### 本地调用

```bash
node skills/deepwiki-query/scripts/deepwiki-projects.js
node skills/deepwiki-query/scripts/deepwiki.js https://github.com/owner/repo
node skills/deepwiki-query/scripts/deepwiki-page.js https://github.com/owner/repo architecture-overview
node skills/deepwiki-query/scripts/deepwiki-chat.js https://github.com/owner/repo
```

也支持简写仓库地址，例如：

```bash
node skills/deepwiki-query/scripts/deepwiki.js github:owner/repo zh
```

### 四个入口说明

1. `deepwiki-projects.js`
   - 用途：列出 DeepWiki 中已经处理过的项目
   - 参数：`[language]`

2. `deepwiki.js`
   - 用途：查看项目 Wiki 结构总览
   - 参数：`<repo_url> [language]`

3. `deepwiki-page.js`
   - 用途：查看指定页面的 Markdown 内容
   - 参数：`<repo_url> <page_id> [language]`

4. `deepwiki-chat.js`
   - 用途：输出适合继续追问的项目导览信息
   - 参数：`<repo_url> [language]`

### 服务器部署场景

如果 DeepWiki 部署在服务器上：
- 保持后端服务可访问
- 在 Claude Code 运行机器上设置 `DEEPWIKI_BASE_URL`
- 不需要 MCP、stdio、SSH 拉起远端 Python 进程

示例：

```bash
export DEEPWIKI_BASE_URL="http://your-server:8001"
```

如果服务器只在内网可访问，也可以通过 VPN、跳板机或反向代理方式，让 Claude Code 所在机器访问到该 HTTP 地址。

### 注意事项

- 目标仓库必须已经在 DeepWiki 中生成过 Wiki
- 当前 skill 只支持查询，不支持创建任务
- 后端未启动时 skill 会查询失败
- 后端需要提供现有接口：`GET /api/processed_projects` 与 `GET /api/wiki_cache`
- skill 文件位于项目内 `skills/deepwiki-query/`，便于团队后续安装或同步到 `~/.claude/skills`

### 为什么推荐 skill 而不是 MCP

- 不依赖 MCP 运行时，避免额外的 Python 依赖冲突
- 直接通过 HTTP 调用现有后端接口，部署关系更简单
- 团队可以直接复用仓库内 skill 目录，便于安装与同步
- 更适合后续服务器部署，只需保证 Claude Code 到后端 HTTP 地址可达

---

## 启动顺序

先启动后端，等看到 `Uvicorn running` 后再启动前端。

如果要使用 Claude Code skill，请在后端启动并确认 Wiki 缓存存在后，再运行 skill 脚本或在 Claude Code 中调用对应命令。
