# DeepWiki Open

AI驱动的代码仓库文档生成工具。输入任意Git仓库，自动分析代码结构，生成结构化的技术文档。

## 源码地址

- **GitHub**: https://github.com/AsyncFuncAI/deepwiki-open
- **Gitee**: https://gitee.com/deepwiki/deepwiki-open

## 功能特性

- **智能文档生成**：自动分析代码仓库，生成 Markdown 格式的技术文档
- **架构可视化**：自动生成 Mermaid 架构图、流程图、时序图
- **多平台支持**：GitHub、GitLab、Bitbucket、本地仓库
- **多语言输出**：支持中文、英文、日文等多种语言
- **AI 知识问答**：基于文档内容，实时问答交互
- **一键导出**：支持导出为 Markdown 或 JSON 格式

## 技术栈

- **前端**：Next.js 15 + TypeScript + Tailwind CSS
- **后端**：Python FastAPI
- **AI 模型**：OpenAI GPT、SiliconFlow、MiniMax 等
- **部署**：Docker + Docker Compose

## 环境要求

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose（部署用）

## 快速开始

### 本地开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 后端 API 服务（另一个终端）
cd api
uvicorn api.main:app --reload --port 8001
```

### Docker 部署

#### 方式一：服务器构建（推荐）

```bash
# 1. 克隆代码
git clone https://github.com/AsyncFuncAI/deepwiki-open.git
cd deepwiki-open

# 2. 配置环境变量
cp .env.example .env
vim .env  # 编辑必要的 API Key

# 3. 构建并启动
docker-compose up -d

# 4. 查看状态
docker-compose ps
```

#### 方式二：本地打包后上传

```bash
# 1. 本地构建镜像
docker build -t deepwiki .

# 2. 导出镜像
docker save deepwiki -o deepwiki.tar

# 3. 上传到服务器
scp deepwiki.tar user@server:/opt/deepwiki/

# 4. 服务器加载并启动
docker load < deepwiki.tar
docker-compose up -d
```

## 环境变量说明

| 变量 | 说明 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 是 |
| `MINIMAX_API_KEY` | MiniMax API 密钥 | 是 |
| `SERVER_BASE_URL` | 后端服务地址 | 是 |
| `FRONTEND_PORT` | 前端端口（默认 3000） | 否 |
| `BACKEND_PORT` | 后端端口（默认 8001） | 否 |

## 目录结构

```
├── api/                    # Python 后端代码
│   ├── api/               # API 路由和业务逻辑
│   └── main.py            # FastAPI 入口
├── src/                   # Next.js 前端代码
│   ├── app/              # 页面组件
│   └── components/        # 可复用组件
├── public/               # 静态资源
├── Dockerfile            # Docker 构建配置
└── docker-compose.yml   # 服务编排配置
```

## API 服务

后端提供以下主要接口：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/wiki/structure` | POST | 生成文档结构 |
| `/api/wiki/content` | POST | 生成页面内容 |
| `/api/chat/stream` | WebSocket | AI 问答流式响应 |
| `/api/wiki/export` | GET | 导出文档 |

## 许可证

MIT License
