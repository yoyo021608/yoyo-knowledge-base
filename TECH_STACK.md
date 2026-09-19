# 技术栈

本文件记录项目当前确定的技术选型和版本基线。代码目录和依赖方向以 `docs/architecture.md`、`AGENTS.md` 为准。

## 版本基线

| 层次 | 选择 | 用途 |
| --- | --- | --- |
| 运行环境 | Node.js 22.13+ | 前端工具链和 Monorepo 脚本 |
| 包管理 | pnpm 11.26.0 | Workspace 依赖管理 |
| 后端运行环境 | Python 3.12+ | FastAPI 服务和后台任务 |
| 主数据库 | PostgreSQL 16 | 用户、文档、版本、会话和问答数据 |
| 缓存与任务 | Redis 7 | 缓存、短期状态和索引刷新任务 |
| 本地依赖 | Docker Compose | PostgreSQL、Redis 等开发依赖编排 |

## 前端

- React 18：构建正式 Web 界面，不使用纯 HTML 页面作为正式前端方案。
- TypeScript：约束页面、业务状态和 API 数据结构。
- Vite：开发服务器和前端构建工具。
- React Router：前端路由和页面导航。
- Vitest：前端单元测试和组件测试。

当前仓库只安装到上面这些。以下选型在对应功能开始时引入，尚未落地：

- TanStack Query：服务端数据请求、缓存和失效刷新。
- Zustand：保存适合放在客户端的轻量交互状态。
- Tailwind CSS：基础样式体系。
- shadcn/ui：可组合的通用 UI 组件，不承载具体业务规则。
- Playwright：注册、录入、问答等关键用户流程测试。
- ESLint + Prettier：前端静态检查和格式化。

前端使用 pnpm Monorepo，并分离业务层与 UI 层：

- `apps/web`：路由、页面入口、Provider、平台环境变量和平台装配。
- `packages/core`：不依赖 React 的无头业务能力、领域类型和 API 客户端。
- `packages/ui`：不依赖业务包的展示组件、样式和通用交互。
- `packages/views`：把 `core` 与 `ui` 组合成页面级视图。

## 后端

- FastAPI：统一暴露 HTTP API、OpenAPI 文档和依赖注入入口。
- Uvicorn：运行 ASGI 服务。
- Pydantic v2：请求、响应、配置和边界数据校验。
- SQLAlchemy 2.x：PostgreSQL 映射和查询。
- Alembic：数据库结构迁移。
- psycopg 3：PostgreSQL 驱动，连接串使用 `postgresql+psycopg://`。
- pwdlib + Argon2：密码摘要和密码校验。
- PyJWT：登录凭证签发和校验。
- pytest + pytest-asyncio + httpx：后端单元测试和接口测试。
- Ruff：Python lint 和基础格式检查。
- Black：Python 代码格式化。
- mypy：Python 类型检查。

后端按领域拆包：`apps/api` 负责启动、HTTP 装配和跨模块用例协调，`packages/backend/users`、`documents`、`agent`、`sessions` 负责各自业务，`clients` 只对接外部 SDK 或服务，`infra` 提供数据库、缓存、文件和任务基础设施。跨模块协调只组合 controller/Port，不拥有领域数据，也不能变成通用 `services` 包；同层模块不能互相深入调用。

## 数据与检索

- PostgreSQL 16：系统核心数据的唯一事实来源。
- PostgreSQL Full Text Search：关键词和全文检索。
- pgvector：保存 Embedding 并支持向量近邻检索。
- 混合检索：结合关键词、全文和向量召回，再由 Agent 组织上下文。
- Redis 7：保存可过期、可重建或待执行的短期数据，不作为核心数据的唯一来源。
- 文件存储：第一阶段使用本地目录适配，后续可替换为对象存储；文件内容和文档业务关系分离。

## AI 能力

- `LLM_PROVIDER=fake`：本地开发和自动化测试的默认模式。
- `LLM_PROVIDER=openai` 或其他 OpenAI 兼容服务：接入真实模型时使用。
- OpenAI 官方 SDK 或兼容 SDK：由 `packages/backend/clients` 直接对接，Agent 通过明确的依赖使用，不再包装多层通用 Provider。
- Chat Model：负责问题改写、回答生成和必要的内容处理。
- Embedding Model：负责文档切分后的向量生成。
- RAG：Agent 负责问题改写、检索编排、证据判断、上下文组装和回答引用；documents 负责知识切分、索引、召回和结果融合。

基础设施模块只读取并校验模型配置；外部 SDK 连接归 `clients`，Agent 不直接访问文档数据库或向量库。

## 工程化与部署

- Docker / Docker Compose：本地依赖和开发环境。
- GitHub Actions：格式检查、测试和构建检查。
- `.env.example`：只保存变量名和本地安全默认值，不保存真实密钥。
- GitHub Issue + Pull Request：按“小功能一个 Issue、一个 PR 关联一个 Issue”的方式协作。

## 不采用的方案

- 不采用纯 HTML + 零散脚本作为正式前端。
- 不使用混合启动与业务的 `server` 目录；FastAPI 启动放在 `apps/api`，后端领域逻辑放在 `packages/backend`。
- 不把所有业务塞进 `api` 或通用 `utils`。
- 不建立通用 `apps/api/ai` 或过度抽象的模型 Provider 层。
- 不只做向量检索；必须保留结构化数据、关键词检索、重排、证据门槛和来源引用。
- 不把 Redis 或向量索引当作核心业务数据的唯一来源。
