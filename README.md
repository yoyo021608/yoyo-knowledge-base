# yoyo-knowledge-base

面向个人知识收录、组织、检索与问答的 Web 应用。系统把文档、笔记、网页链接和上传资料统一纳入知识库，支持专题、标签、收藏、关联、来源追溯、版本保留、索引刷新，以及带引用的知识问答。

改代码前请先阅读 `docs/total-design.md`、`docs/architecture.md`、`AGENTS.md` 和对应的 `docs/modules/` 模块文档。

## 本地运行

需要 [Node.js](https://nodejs.org/) 22.13+、[pnpm](https://pnpm.io/) 11.17.0、[Python](https://www.python.org/) 3.12+、[PostgreSQL](https://www.postgresql.org/) 16 和 [Redis](https://redis.io/) 7。默认 `LLM_PROVIDER=fake`，不需要先配置模型 Key。

项目按“产品设计 → 架构设计 → 模块设计 → 代码实现”的顺序推进。代码骨架完成后，可以使用下面的命令启动开发环境：

~~~bash
cp .env.example .env
pnpm install
pnpm dev
~~~

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

`.env` 只用于本地运行，不要提交到 GitHub。接入真实模型时填写 `OPENAI_API_KEY`；使用 `LLM_PROVIDER=fake` 时可以保持为空。

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

- `docs/total-design.md`：产品形态、完整功能、数据对象和总体流程
- `docs/architecture.md`：目录归属、分层边界、依赖方向和跨模块联动规则
- `docs/modules/auth.md`：认证模块详细设计
- `docs/modules/documents.md`：文档与知识组织模块详细设计
- `docs/modules/agent.md`：Agent、RAG 与运行控制详细设计
- `docs/modules/sessions.md`：会话、消息和引用回放模块详细设计
- `docs/modules/infra.md`：基础设施模块详细设计
- `AGENTS.md`：目录放置规则、边界规则和协作约束
- `TECH_STACK.md`：确定的技术选型和使用范围

## 目录

~~~text
yoyo-knowledge-base/
├── apps/web/       # React Web 应用
├── packages/       # 前端无头业务、UI 和页面组合包
├── server/app/     # FastAPI 应用和领域模块
├── docs/           # 产品、架构和模块设计文档
├── scripts/        # 一次性开发脚本
├── brand/          # 品牌与展示素材
├── .github/        # Issue、PR 和 CI 配置
├── AGENTS.md
├── README.md
├── TECH_STACK.md
├── .env.example
└── LICENSE
~~~

## 参与开发

从 `main` 开分支，按 `docs/architecture.md` 和 `AGENTS.md` 放置代码。一个明确功能对应一个 Issue 和一个 Pull Request；Pull Request 必须关联对应 Issue，并说明改了什么、为什么改、如何验证。较大的产品行为或模块边界变化，先更新设计文档再进入实现。

## 项目范围

项目聚焦于个人知识资料的收录、组织、检索、问答和来源追溯，覆盖账户认证、文档单个与批量录入、资料展示与维护、专题标签、收藏关联、版本管理、索引刷新、会话历史和 Agent 运行控制。

## License

[MIT](LICENSE)
