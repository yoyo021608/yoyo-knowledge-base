# 架构文档

## 1. 架构目标

- 让知识收录、检索、问答和来源追溯各自有清晰边界。
- 让 React 前端、FastAPI 后端和基础设施彼此分离。
- 让模块可以通过接口联动，但不能把别的模块业务复制到自己目录。
- 让文档版本、来源快照、会话引用和回答结果形成可追溯链路。
- 让会话运行能够在断线或进程重启后恢复。
- 让检索结果经过过滤、重排和证据判断后再进入模型上下文。
- 让一个功能能够定位到一个领域模块、一个 Issue 和一个 Pull Request。

本文说明模块怎么分、边界在哪、目录怎么放，以及模块之间怎么联动。具体模块内部设计见 `docs/modules/`。

本文只保留架构层面的职责和关系，不重复产品功能清单。完整功能行为见 `docs/total-design.md`，模块内部设计见 `docs/modules/`，跨模块数据流见 `docs/flows/`。

## 2. 架构图与目录划分

![架构图](diagrams/architecture.png)

架构图使用 draw.io 维护，源文件是 `docs/diagrams/architecture.drawio`，导出文件是 `docs/diagrams/architecture.png`。业务流程使用文字或 flowchart 表达，不塞进架构图。

代码目录划分如下：

~~~text
yoyo-knowledge-base/
├── README.md
├── TECH_STACK.md
├── AGENTS.md
├── LICENSE
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── .github/
├── apps/
│   └── web/
├── server/
│   ├── main.py
│   ├── config.py
│   ├── controller/
│   ├── users/
│   ├── documents/
│   ├── sessions/
│   ├── agent/
│   └── infra/
├── packages/
│   ├── core/
│   ├── ui/
│   └── views/
├── tests/
├── data/
├── scripts/
├── docs/
│   ├── total-design.md
│   ├── architecture.md
│   ├── mvp.md
│   ├── flows/
│   ├── diagrams/
│   └── modules/
└── brand/
~~~

目录树说明职责归属；具体文件在对应职责进入实现时创建，模块目录与具体职责对应。`server/main.py` 是启动和装配入口，不是新的业务模块；业务归属于 `server` 下的领域包。`packages` 只放前端共享包和页面组合，不放 Python 后端。

## 3. 模块职责与边界

后端划分为 users、documents、sessions、agent、infra 五个职责模块，其中前四个是业务模块，infra 提供技术支持。controller 与五个模块同级，承担统一接入和调用协调，不另算业务模块：

| 模块 | 负责 | 不负责 |
| --- | --- | --- |
| 账户（`users`） | 注册、登录、修改密码、忘记密码、注销和当前用户身份 | 不判断某条资料或某个会话该不该被访问 |
| 文档（`documents`） | 文档、版本、来源、片段、知识点、实体、关系、索引状态，以及受归属和版本约束的知识查询端口 | 不决定本轮检索策略，不做问题改写、证据判断和回答生成 |
| 编排（`agent`） | 检索、研究、对比、学习、证据判断、回答、评估和运行控制 | 不拥有文档、版本、片段、索引和会话消息 |
| 会话（`sessions`） | 对话、研究任务、练习记录、回答、引用和用户反馈的保存与回放 | 不负责知识解析、检索策略、回答生成和模型调用 |
| 基础设施（`infra`） | 数据库、缓存、文件、后台任务、模型连接和资源生命周期 | 不做产品业务判断 |

上表是模块级摘要：它说明数据和职责归属，不展开注册、导出、研究、对比或学习等具体功能。具体功能行为由产品设计文档说明，功能内部如何拆分由对应模块文档说明。

非业务支持包：

- `agent/rag` 是 Agent 的子能力，负责“本轮如何检索和使用知识”；文档内容、版本、切分、知识点、实体、关系和索引状态归 `documents`，索引引擎连接归 `infra`。
- `agent/tools` 是适配层，负责工具定义、参数、权限和结果转换；不保存文档，不包办文档检索。
- `agent/prompts` 集中存放系统提示和任务提示，提示词不散落在业务流程中。
- `controller` 接收 HTTP 请求并组合模块公开接口；不拥有领域数据，不直接查询业务表。
- `infra` 提供数据库、缓存、文件、任务和模型 SDK 连接；不反向依赖业务模块。documents 维护索引对象与版本状态，infra 提供向量数据库和全文引擎连接；检索策略、重排和证据判断归 agent。

前端包：

- `apps/web`：Web 路由、页面入口、Provider、前端环境变量和平台装配。
- `packages/core`：无头业务能力、领域类型、API 客户端和纯逻辑；不依赖 React、DOM 或平台环境变量。
- `packages/ui`：无业务 UI、通用组件、样式和交互基础设施；不依赖 `core`。
- `packages/views`：按业务域组合 `core` 与 `ui` 为页面视图；不读取平台环境变量，不承担平台路由。

## 4. 模块联动与架构约束

### 分层与依赖方向

前端依赖方向固定为：

~~~text
apps/web → packages/views → packages/core
                    ↓
                packages/ui
~~~

`packages/ui` 不反向依赖 `packages/core`。CLI 接入仅依赖 `packages/core`，不能依赖 React 页面和路由层。

后端依赖方向为：

~~~text
server/main.py：创建应用、注入依赖、挂载 controller 路由
  → server/controller：HTTP 接入与模块调用协调
  → users / documents / sessions / agent：各自的公开业务接口
  → infra：数据库、缓存、文件、任务和 SDK 连接

agent/rag / tools → 注入的 DocumentSearchPort → documents
controller → sessions 的消息接口与 agent 的运行接口
~~~

- server/main.py 只负责启动、配置和依赖装配；业务逻辑归 server 下的领域模块，HTTP 接入归 server/controller。
- controller 负责解析请求、取得可信身份、参数校验、组合模块调用和转换响应；不直接操作数据库、不实现检索算法、提示词策略或领域状态规则。
- controller 中的协调函数与 HTTP 请求对象解耦，供路由和由启动入口注册的恢复任务复用；无需单独建立 application 包。
- users、documents、sessions、agent 通过公开接口提供能力，内部维护自己的模型、规则和数据访问；不再各自设置同名 controller 入口。
- 同层业务实现不得相互导入；跨模块调用使用明确的接口契约并由启动入口注入，禁止跨模块直接查表或修改内部数据。
- Agent 的工具负责参数与结果适配，文档切分、索引状态、知识关系和基础查询归 documents；问题改写、检索组合、重排、证据判断与上下文选择归 agent。
- infra 直接使用 SDK 提供连接和必要的轻量适配，不建立多层模型 Provider；领域模块不自行创建外部客户端。
- 业务模块不依赖 FastAPI 路由、controller 或 apps；公开结果不直接返回 ORM 对象。
- 每个模块按业务需要组织内部文件，不建立承载多个领域业务的公共 services、utils 或 repository。

### 模块联动规则

- 文档编辑产生新的版本，索引只面向最新版本；旧版本和来源快照用于追溯。
- 回答引用由 `agent` 产生，controller 调用 `sessions` 保存，始终绑定具体文档版本或来源快照。
- 过程事件、取消、继续和断线恢复属于 `agent` 的运行控制，不放进 `sessions`。
- `sessions` 只保存活动 Run 关联，不拥有 Run；删除会话先标记 deleting，阻止提问和迟到写入，再由协调方调用 agent 清理运行，最后删除会话数据；定期扫描 deleting 会话补偿清理，不能仅依赖 Run 扫描。
- 活动 Run 仅在会话有效且关联为空时原子领取，同 Run 重试幂等；并发提问返回忙碌，不保存额外问题。释放必须匹配 runID，避免旧任务清掉新关联。
- Run 进入 `completed`、`cancelled` 或 `failed` 等终态时，controller 协调流程必须清理对应的 `active_run_id`；只有仍可继续的运行状态可以保留关联。
- 工具通过注入的 Port 使用其他模块能力；工具不得直接导入其他模块的内部业务实现。
- 用户身份由认证入口提供，各领域校验自己资源的归属；模型和请求正文不能覆盖身份。
- 完整回答先存入 Agent 快照，BeginFinalize 条件领取最终提交权，与取消互斥；随后 sessions.SaveAnswer 按 Run 幂等且同事务保存消息与引用，再完成 Run、释放关联，失败时可重复协调。
- controller 的协调函数由路由或后台任务调用，后台任务由 server/main.py 注册并管理生命周期；任务调度归 infra，运行状态与恢复资格归 agent。
- 系统使用单执行进程；启动及定期扫描未完成 Run，正常执行与恢复共用 Run 互斥锁，跳过仍在执行的任务；遗留 running 转 paused，finalizing 只重试保存。领取或消息保存中断可按 requestID/runID 重试；未获关联的 queued Run 标记失败，终态残留关联按 runID 清理。
- 事件回放不等于执行恢复；步骤快照与对应事件同事务持久化。生成中断重新生成该轮，旧的部分输出标记中断。
- 索引任务绑定版本并条件发布；最新版本未 ready 不使用旧索引，删除和归档立即影响查询过滤。
- 上下文窗口扣除输出预留与安全余量后，分别限制历史和证据，所有模型调用复核 token；默认最多补查 1 次且总检索不超过 30 秒，均可配置。
- 原文存在时引用可定位旧版本；删除后只保留回答内的摘录、标题、网址和版本标识，完整原文不可回放。

## 5. 模块联动示例

完整业务流程见 `docs/flows/`。架构图只表达模块和依赖关系，不承担业务流程说明。

RAG 是 Agent 的子能力：RAG 负责“本轮如何检索和使用知识”，documents 负责“知识如何保存、切分、组织和建立索引”。一次问答的调用链是：

~~~text
用户问题
  ↓
server/controller：解析请求并取得当前用户
  ↓
server/controller：校验会话归属和状态
  ↓
agent 公开接口：创建 queued Run
  ↓
server/controller：条件领取活动 Run；失败则标记 failed 并返回忙碌
  ↓
server/controller：按 Run 幂等保存 User Message，再启动执行
  ↓
agent/rag：问题改写与检索计划
  ↓
DocumentSearchPort
  ↓
documents：按用户归属、文档状态和 ready 版本提供候选片段
  ↓
agent/rag：重排、证据判断和上下文组装；证据不足有限次改写补查
  ↓
agent：使用注入的 infra 模型连接生成回答
  ↓
agent：持久化完整结果快照
  ↓
server/controller：BeginFinalize 领取提交权，sessions.SaveAnswer 幂等保存回答与引用，再完成 Run 并释放关联
~~~

用户先注册账号并登录，把一篇网页文章和一份 Markdown 笔记录入知识库，打上标签并归入专题。一周后他新建会话提问，系统同时进行全文和向量召回，融合排序后筛出相关片段。

如果第一次检索的证据不足，Agent 只有限次改写查询并请求 documents 重新检索；仍不足就返回明确的“知识库证据不足”，不让模型编造确定结论。回答完成后，引用绑定当时的文档版本和来源快照。

用户后来修改文档，documents 生成新版本并刷新索引；旧回答仍然可以回到旧版本。提问过程中用户可以取消或继续 Run；如果中途断网，重新进入后按照事件序号补回已经产生的过程。

## 6. 关键取舍

- **为什么使用全文与向量混合检索**：型号、错误码等精确词需要关键词命中，同义表达又需要向量召回；两者结合比只做一种更适合个人资料。
- **为什么 RAG 是 Agent 子包**：问题改写、检索组合、是否重检索和证据判断都服务于当前这轮任务；独立成业务模块会制造额外的双向依赖。文档切分、知识组织和索引状态归 documents，索引引擎连接归 infra。
- **为什么引用绑定版本和来源快照**：文档会被改写、网页来源也可能失效，只绑定文档本身无法还原历史回答依据。
- **为什么事件先持久化再推送**：流式通知断线会丢失，带序号持久化后才能按缺口回放。
- **采用哪些流程思想**：入库与问答分开，召回后重排；执行用步骤快照恢复，展示用事件回放；检索用标注问题集评估。这些机制由各业务模块通过明确接口组合，不引入完整工作流或 RAG 框架。
- **为什么把 Python 后端放在 server**：FastAPI 启动、Python 领域模块和基础设施属于同一后端运行单元，放在与前端 `packages` 同级的 `server` 更容易表达归属；前端仍采用 React 和 TypeScript 的 monorepo。
- **为什么不设全局 `utils`、`services` 或 `repository`**：业务逻辑归属明确的领域模块；跨模块复用由能力所属模块通过 Port 暴露。

这些模块边界对应具体的设计借鉴：RAGFlow 对应 documents 的解析、片段和索引状态；NexusRAG 对应 agent 的混合检索、重排和引用；GraphRAG 对应 documents 的实体与关系；LangGraph 对应 agent 的 Run 快照和恢复；Ragas、Langfuse 对应 agent 的评估和 infra 的运行追踪。借鉴的是解决问题的机制，数据归属仍按本项目的四个模块执行。

## 7. 设计问题回答

### 知识怎么建模和组织，为什么利于检索

资料以“文档 + 版本”建模，正文修改产生新版本；当前版本用于检索，历史版本和来源快照用于追溯。专题、标签和文档关联是可交叉的组织维度，一篇资料可归入一个专题、带多个标签并关联其他资料。这些维度也可以成为检索过滤条件，先缩小范围再计算相关度。

### 检索链路怎么设计，检索不准时怎么办

controller读取会话历史并交给 Agent。Agent 结合问题和会话上下文改写查询，决定关键词、全文、向量或混合检索的组合，再通过 `DocumentSearchPort` 请求 documents 返回候选。documents 负责知识归属、版本过滤、索引状态和基础候选查询；Agent 负责候选融合、重排、证据判断、上下文预算和是否重查。证据门槛不通过时有限次改写和重检索，仍不足则返回证据不足；服务异常或超时单独返回故障，不混为检索无结果。

### Agent 或工作流怎么处理一步答不好的问题

不引入没有必要的多 Agent 层。一次回答由可恢复的 Run 组织；检索证据不足走改写和有限重检索，外部调用失败走有限重试，回答生成后检查 Citation。步骤结果与事件同事务保存；断线按序号回放，重启复用已完成步骤，生成中断重新生成该轮，无法继续时保留可识别失败状态。

### 怎么评估检索质量

为代表性问题保留期望文档或版本作为小型标注集，检查正确来源是否进入前 `K` 个结果、是否排在更前面、证据门槛是否拦住无依据回答，并记录 `Recall@K`、`MRR@K`、引用命中率和证据不足误判率。MVP 同时记录命中数量、二次检索触发率和失败原因；评估结果用于调整检索策略，不改变 documents 的数据所有权。

MVP 功能范围和验收条件统一见 `docs/mvp.md`，本架构文档只说明支撑该范围所需的模块边界和依赖方向。
