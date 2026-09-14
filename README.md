# yoyo-knowledge-base

面向个人知识收录、组织、检索与问答的 Web 应用。系统把文档、笔记、网页链接和上传资料统一纳入知识库，支持专题、标签、收藏、关联、来源追溯、版本保留、索引刷新，以及带引用的知识问答。

改代码前请先阅读 `docs/total-design.md`、`docs/architecture.md`、`AGENTS.md` 和对应的 `docs/modules/` 模块文档。

## 本地运行

需要 [Node.js](https://nodejs.org/) 22.13+、[pnpm](https://pnpm.io/) 11+、[Python](https://www.python.org/) 3.12+、[PostgreSQL](https://www.postgresql.org/) 16 和 [Redis](https://redis.io/) 7。默认 `LLM_PROVIDER=fake`，不需要先配置模型 Key。

项目按“产品设计 → 架构设计 → 模块设计 → 代码实现”的顺序推进。代码骨架完成后，按下面的顺序启动开发环境：

~~~bash
# 1. 启动本地依赖服务
docker compose up -d postgres redis

# 2. 准备环境变量
cp .env.example .env

# 3. 创建并激活 Python 虚拟环境
python -m venv server/.venv
source server/.venv/bin/activate
cd server
python -m pip install --editable ".[dev]"
cd ..

# 4. 安装前端依赖
pnpm install

# 5. 启动前后端
pnpm dev
~~~

`docker-compose.yml` 只编排 PostgreSQL、Redis 这类本地依赖服务，前后端本身由 `pnpm dev` 直接启动，所以仓库不放 Dockerfile。停止依赖服务用 `docker compose down`。

也可以分开启动：

~~~bash
pnpm dev:api
pnpm dev:web
~~~

默认地址：

- API：`http://localhost:8000`
- Web：`http://localhost:5173`
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

Windows PowerShell 可以用下面的命令复制环境变量模板：

~~~powershell
Copy-Item .env.example .env
~~~

Windows PowerShell 的 Python 环境准备命令如下：

~~~powershell
python -m venv server\.venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\server\.venv\Scripts\Activate.ps1
Set-Location server
python -m pip install --editable ".[dev]"
Set-Location ..
pnpm install
~~~

每次新开终端运行后端命令前，都需要重新激活 `server/.venv`。退出虚拟环境使用 `deactivate`。

`.env` 只用于本地运行，不要提交到 GitHub。接入真实模型时填写 `OPENAI_API_KEY`；使用 `LLM_PROVIDER=fake` 时可以保持为空。

默认数据库配置为 `DATABASE_URL=postgresql+psycopg://postgres:change-me@localhost:5432/knowledge_base` 和 `REDIS_URL=redis://localhost:6379/0`，与 `.env.example` 保持一致。用 `docker compose up -d postgres redis` 启动的服务可以直接使用默认值；如果本机 PostgreSQL 的账号、密码或端口不同，改 `.env` 里这两个变量即可。

## 测试

代码骨架完成后，仓库级命令统一从根目录执行：

~~~bash
pnpm test
pnpm lint
~~~

也可以按技术栈分别检查：

~~~bash
cd server
pytest
ruff check .
mypy .

cd ../apps/web
pnpm test
pnpm lint
~~~

后端接口测试使用 pytest 和 httpx；前端组件测试使用 Vitest，关键用户流程使用 Playwright。新增功能时，先补对应模块的单元测试或接口测试，再提交 PR。

## 文档入口

- `docs/total-design.md`：产品形态、为什么需要它和完整功能清单
- `docs/architecture.md`：分层与目录归属、模块边界、依赖方向和跨模块联动规则
- `docs/modules/users.md`：账户模块详细设计
- `docs/modules/documents.md`：文档与知识组织模块详细设计
- `docs/modules/agent.md`：Agent、RAG 与运行控制详细设计
- `docs/modules/sessions.md`：会话、消息和引用回放模块详细设计
- `docs/modules/infra.md`：基础设施模块详细设计
- `AGENTS.md`：目录放置规则、边界规则和协作约束
- `TECH_STACK.md`：确定的技术选型和使用范围

## 目录

~~~text
yoyo-knowledge-base/
├── README.md
├── TECH_STACK.md
├── AGENTS.md
├── docker-compose.yml   # 本地依赖服务编排
├── .env.example
├── .github/             # Issue、PR 和 CI 配置
├── apps/web/            # React Web 应用
├── packages/            # 前端无头业务、UI 和页面组合包
├── server/              # FastAPI 应用、领域模块和数据库迁移
├── tests/               # 后端测试
├── data/                # 运行时数据
├── docs/                # 产品、架构和模块设计文档
├── scripts/             # 一次性开发脚本
└── brand/               # 品牌与展示素材
~~~

目录树说明职责归属；具体文件在对应职责开始实现时创建。

## 参与开发

从 `main` 开分支，按 `docs/architecture.md` 和 `AGENTS.md` 放置代码。一个明确功能对应一个 Issue 和一个 Pull Request；Pull Request 必须关联对应 Issue，并说明改了什么、为什么改、如何验证。较大的产品行为或模块边界变化，先更新设计文档再进入实现。

## 项目范围

项目聚焦于个人知识资料的收录、组织、检索、问答和来源追溯，覆盖账户认证、文档单个与批量录入、资料展示与维护、专题标签、收藏关联、版本管理、索引刷新、资料导出、会话历史和 Agent 运行控制。

## License

[MIT](LICENSE)
