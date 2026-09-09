# 架构文档

## 1. 架构目标

- 让知识收录、检索、问答和来源追溯各自有清晰边界。
- 让 React 前端、FastAPI 后端和基础设施彼此分离。
- 让模块可以通过接口联动，但不能把别的模块业务复制到自己目录。
- 让文档版本、来源快照、会话引用和回答结果形成可追溯链路。
- 让一个功能能够定位到一个领域模块、一个 Issue 和一个 Pull Request。

架构图使用 draw.io 维护，本文负责说明目录归属、依赖方向和模块边界；业务流程使用 flowchart 表达。

## 2. 目录归属图

~~~text
yoyo-knowledge-base/
├── README.md
├── TECH_STACK.md
├── AGENTS.md
├── .env.example
├── apps/
│   └── web/
├── packages/
│   ├── core/
│   ├── ui/
│   └── views/
├── server/
│   └── app/
│       ├── main.py
│       ├── api/
│       ├── auth/
│       ├── documents/
│       ├── agent/
│       │   ├── rag/
│       │   └── tools/
│       ├── sessions/
│       └── infra/
├── migrations/
├── scripts/
├── brand/
├── docs/
│   ├── total-design.md
│   ├── architecture.md
│   └── modules/
└── .github/
~~~

目录图用于说明代码职责归属，具体文件划分以实际实现为准。目录只有在对应职责进入实现时才需要建立实际代码文件。

## 3. 前端架构

- `apps/web`：Web 路由、页面入口、Provider、前端环境变量和平台装配。
- `packages/core`：无头业务能力、领域类型、API 客户端和纯逻辑；不依赖 React、DOM、Next 或 `process.env`。
- `packages/ui`：无业务 UI、通用组件、样式和交互基础设施；不依赖 `core`。
- `packages/views`：按业务域把 `core` 与 `ui` 组合为页面视图；不读取平台环境变量，不直接依赖路由框架。

前端依赖方向固定为：

~~~text
apps/web → packages/views → packages/core
                    ↓
                packages/ui
~~~

`packages/ui` 不反向依赖 `packages/core`。未来如果增加 CLI，只允许依赖 `packages/core`，不能依赖 React 页面和路由层。

## 4. 后端架构

后端使用 Python + FastAPI，统一入口是 `server/app/main.py`：

- `app/main.py`：启动、配置读取、Router 组装、依赖注入和生命周期。
- `app/api`：HTTP 路由、请求/响应 DTO、参数校验、认证依赖和响应组装。
- `app/auth`：用户注册、登录、忘记密码、密码重置和注销。
- `app/documents`：单个录入、批量录入、列表、详情、编辑、专题、标签、收藏、关联、版本、来源和索引刷新。
- `app/agent`：问题改写、检索编排、工具适配、回答生成、引用选择和运行控制。
- `app/agent/rag`：与 Agent 强绑定的 RAG 子包，负责检索计划、上下文组装、回答生成和证据判断。
- `app/agent/tools`：工具定义、参数、权限、结果适配和 Port 调用。
- `app/sessions`：会话、消息、会话改名、历史记录和回答引用回放。
- `app/infra`：数据库、缓存、后台任务、文件存储和模型配置。

后端依赖方向为：`app/api` 调用领域模块，领域模块调用 `app/infra` 或显式 Port，`app/infra` 不反向依赖业务模块。

## 5. 领域所有权

| 数据或能力 | 所属模块 | 其他模块如何使用 |
| --- | --- | --- |
| User、登录凭证、密码重置 | auth | 通过当前用户身份依赖使用 |
| Topic、Tag、Document、DocumentVersion、SourceSnapshot、收藏和关联 | documents | 通过查询 Port、引用和 DTO 使用 |
| Run、RunEvent、工具调用、取消/继续状态 | agent | 通过运行接口和事件回放使用 |
| Session、Message、Citation | sessions | 由 Agent 在完成运行后写入或读取 |
| 数据库、Redis、文件和模型配置 | infra | 以基础能力方式注入 |

## 6. Agent、RAG 与 Document 联动

RAG 是 Agent 的子能力。RAG 负责“如何检索和使用知识”，documents 负责“知识如何保存、切分、索引和被检索”。

~~~text
用户问题
  ↓
agent/rag：问题改写与检索计划
  ↓
agent/tools：工具和参数适配
  ↓
DocumentSearchPort
  ↓
documents：全文、向量和混合检索
  ↓
agent/rag：上下文组装与证据判断
  ↓
Agent：调用模型 SDK 生成回答
  ↓
sessions：保存消息与引用
~~~

Agent 决定是否调用工具；工具只负责参数和结果适配；文档内容、切分、版本、索引和检索数据仍归 documents。

## 7. 运行事件和重连

- Run 的状态、过程事件和事件序号由 agent 运行控制负责。
- 过程事件先持久化，再作为通知发送给客户端。
- 客户端断线重连时，按 `event_seq` 从持久化事件中回放，不能把前端内存当作事实来源。
- 取消和继续都是 Run 状态变化，由 Agent 统一处理；sessions 只保存会话和消息。

## 8. 文档版本、资料更新与索引刷新

1. 文档录入先保存内容、来源和专题归属。
2. 文档编辑、改写或重新导入生成新的 DocumentVersion，旧版本保留。
3. 最新版本进入切分、全文索引和向量索引刷新流程。
4. Redis 任务可以负责异步刷新，但 PostgreSQL 保存任务关联的核心状态。
5. 刷新状态需要能够表示 queued、processing、ready 和 failed，并支持失败重试。
6. 回答引用绑定到具体文档版本或来源快照。

## 9. 模块联动规则

- auth 提供身份，不判断文档内容。
- documents 管理知识本体、组织关系和检索数据，不负责回答生成。
- agent 调用 documents 的能力，不复制 documents 实现。
- sessions 管理对话记录和引用，不负责过程事件和回答策略。
- infra 提供资源访问，不做产品业务判断。
- 跨模块联动使用显式接口、Port 或 DTO，不通过直接修改别的模块内部数据完成。

## 10. 对外接口分层

- `api` 是唯一的 HTTP 暴露层。
- 领域模块提供内部业务方法和 Port，不直接依赖 FastAPI 路由对象。
- 外部接口的请求/响应 DTO 在 `api` 或对应领域的 schema 中定义，不能把 ORM 对象直接作为公开响应。
- SSE 或流式事件由 Agent 的运行控制产生，重连使用事件序号回放。

## 11. 架构约束

- HTTP 路由统一由 `app/api` 暴露，领域业务不能全部写入 `app/api`。
- documents 的文档、版本、来源、索引、收藏和关联逻辑不能复制到 agent。
- agent 只能通过 `DocumentSearchPort` 等显式接口调用文档能力。
- sessions 负责会话、消息和引用，不负责过程事件、取消和重连恢复。
- infra 只提供基础设施能力，不反向依赖业务模块。
- 不使用通用 `utils`、`services` 或 `repository` 包承载所有业务。
- 不创建没有实际职责的通用 `server/app/ai` 或深层 LLM Provider 包装。
- 模型调用直接使用官方 SDK 或兼容 SDK。
- 架构图统一使用 draw.io 维护，本文以目录归属和依赖边界为准。
