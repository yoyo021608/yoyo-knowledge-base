# AGENTS.md

## 目标

这个仓库采用“先产品设计，再架构和模块设计，最后编码”的方式开发。所有代码都必须能够在文档中找到明确归属。需求归属不清时，先阅读 `docs/architecture.md`，再开始编写代码。

## 开发前必读

- `docs/total-design.md`：确认产品范围和功能边界。
- `docs/architecture.md`：确认分层、依赖方向和目录归属。
- 对应的 `docs/modules/*.md`：确认模块职责、数据原型、接口和流程。
- `TECH_STACK.md`：确认技术选型和禁止事项。

## 目录放置规则

- `server/app/main.py`：FastAPI 启动、配置读取、Router 组装、依赖注入和基础生命周期。
- `server/app/api`：HTTP 路由、请求/响应 DTO、参数校验、认证依赖和响应组装；不写领域业务。
- `server/app/users`：注册、登录、修改密码、忘记密码、密码重置、注销和当前用户身份。
- `server/app/documents`：单个录入、批量录入、文档列表、详情、编辑、专题、标签、收藏、关联、来源、版本和索引刷新。
- `server/app/agent`：上下文、问题改写、检索编排、回答生成、引用选择和运行控制。
- `server/app/agent/rag`：与 Agent 强绑定的 RAG 编排，包括问题改写、检索计划、上下文组装、回答生成和证据判断；文档数据与索引实现仍归 `documents`。
- `server/app/agent/tools`：工具定义、入参/出参、权限声明和适配；不保存文档，不实现文档检索细节。
- `server/app/sessions`：会话、消息、会话改名、历史记录和引用回放；不负责回答策略和过程事件。
- `server/app/infra`：数据库连接、缓存、后台任务、文件存储、向量库访问和模型配置；不承载产品业务判断。
- `apps/web`：React 路由、页面入口、Provider、平台装配和前端环境变量。
- `packages/core`：不依赖 React、DOM 或运行时环境变量的无头业务能力、类型和 API 客户端。
- `packages/ui`：通用展示组件、样式和交互基础设施；不依赖 `packages/core`。
- `packages/views`：按业务域组合 `core` 和 `ui`；不直接承担平台路由。
- `docs`：产品、架构和模块设计文档；代码变化较大时先更新文档。

不要创建没有明确职责的业务目录。新增目录必须先能在 `docs/architecture.md` 或对应模块文档中找到职责说明。

## 后端分层规则

- `app/main.py` 负责启动和装配，不负责业务流程。
- `app/api` 只做 HTTP 边界：解析请求、校验参数、调用领域能力、组装响应。
- 领域模块拥有自己的业务对象、业务规则和数据访问逻辑；不要把别的领域的业务实现复制过来。
- `documents` 拥有 `Topic`、`Tag`、`Document`、`DocumentVersion`、来源快照、收藏/关联关系和索引刷新状态。
- `sessions` 拥有 `Session`、`Message` 和 `Citation`，但不拥有回答生成和过程事件。
- `agent` 拥有一次问答运行的编排、工具调用、引用选择和运行状态。
- 过程事件、取消、继续、重连恢复统一放在 `app/agent` 的运行控制中，不放在 `sessions`。
- RAG 编排可以放在 `app/agent/rag`，但文档切分、版本、索引和检索数据必须留在 `documents`。
- 基础设施模块可以被领域模块调用，但 `infra` 不反向依赖领域模块。
- 不创建通用 `utils`、通用 `services`、通用 `repository` 或 `server/app/ai` 来兜底所有业务。
- 数据库查询必须贴近所属领域，不使用一个跨领域的 Generic Store 包装所有查询。

## Agent 与工具边界

- Agent 决定什么时候需要检索、调用哪个工具以及如何组织回答。
- `agent/rag` 负责 RAG 编排，不直接访问文档数据库。
- 工具适配层只负责工具名称、参数、权限、结果格式和外部能力适配。
- 文档内容、切分、版本、索引和检索细节始终属于 `documents`。
- Agent 不直接访问文档数据库；通过 `DocumentSearchPort` 等显式接口获得能力。
- 工具通过注入的 Port 调用外部能力，不在工具内部偷偷导入其他模块的业务实现。
- LLM 和 Embedding 直接使用官方 SDK 或兼容 SDK，不做无收益的多层封装。

## 前端分层规则

- 依赖方向保持 `apps/web` → `packages/views` → `packages/core`，同时 `packages/views` → `packages/ui`。
- `packages/ui` 不依赖 `packages/core`，也不知道 Session、Run、Document 等业务对象。
- `packages/core` 不依赖 React、Next、DOM 或 `process.env`。
- `packages/views` 负责页面级组合，不直接读取平台环境变量，也不承担路由框架细节。
- `apps/web` 负责路由和平台装配，不把业务规则写进页面组件。
- 新业务域只在功能明确后创建，不能提前堆出空目录。

## 数据和事件规则

- PostgreSQL 是核心数据的事实来源。
- Redis 只保存缓存、短期状态和可重试任务，不能替代核心数据表。
- 文档编辑必须生成新的版本记录，再触发索引刷新；不能直接覆盖导致来源丢失。
- 文档收藏、归档和关联关系由 documents 管理，引用只能绑定可追溯的文档版本或来源快照。
- 回答引用必须绑定文档版本或来源快照。
- 流式过程事件是通知，不是真实数据源；重连时按照递增的 `event_seq` 从持久化记录回放。
- 取消或继续运行必须通过 Agent 运行控制改变 Run 状态，不能由前端自行推断最终结果。
- 检索证据不足时，回答必须明确标记证据不足，不能把无依据内容伪装成知识库结论。

## 变更和提交规则

- 先确认需求所属模块，再开始编码。
- 每个明确功能对应一个 Issue；每个 Pull Request 只解决一个明确目标，并关联对应 Issue。
- Issue 颗粒要小，能够说明验收范围。
- PR 必须说明改了什么、为什么改、如何验证。
- 跨模块变化先更新总设计或架构文档，再修改实现。
- 不提交 `.env`、真实密钥、上传文件、数据库文件和构建产物。
