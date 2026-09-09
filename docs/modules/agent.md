# Agent 编排模块（Agent Orchestration）

## 功能职责

Agent 编排模块负责把用户问题组织成一轮完整的知识调用过程，并把运行结果交给会话模块保存。

- 组装当前问题、会话上下文和检索结果。
- 通过 RAG 子包进行问题改写、检索编排和上下文组装。
- 通过工具适配层调用 documents 的检索能力。
- 组织上下文并直接调用模型 SDK 生成回答。
- 判断检索证据是否足够，并规范化回答引用。
- 管理 Run 状态、过程事件、取消、继续和断线重连恢复。

## 边界

- Agent 负责“如何完成一次回答”的编排，不拥有文档、专题、版本和索引数据。
- RAG 是 Agent 的子包，负责检索流程编排；文档内容、切分、版本、索引和检索数据仍属于 documents。
- Agent 不直接访问 documents 的数据库；需要知识时通过 DocumentSearchPort 或工具适配层调用。
- 工具只定义参数、权限和结果适配，不实现文档切分、版本管理和检索算法。
- sessions 负责保存会话、消息和 Citation；Agent 负责产生回答结果和运行事件。
- 模型调用直接使用官方 SDK 或兼容 SDK，不创建没有实际收益的通用 LLM Provider 层。
- 过程事件是可回放的运行通知，最终回答、消息和引用仍然以持久化业务数据为准。
- 证据不足时返回明确状态，不把模型推测伪装成知识库结论。

## 内部拆分

### RAG 编排（RAG Orchestration）

RAG 编排是 Agent 内部的子包，负责把问题、检索、上下文和证据判断串起来；不直接查询文档数据库，也不拥有文档索引。

~~~go
type EvidenceDecision struct {
    Sufficient bool
    Reason string
    HitCount int
}

type RAGPipeline interface {
    Rewrite(input RewriteInput) (RewrittenQuestion, error) // 将用户问题整理为可检索问题。
    Retrieve(plan RetrievalPlan, userID string) ([]SearchHitContext, error) // 通过 Port 获取知识片段。
    AssessEvidence(hits []SearchHitContext) (EvidenceDecision, error) // 判断当前检索结果是否足以支持回答。
    BuildContext(input ContextInput) (ContextPacket, error) // 组装模型调用上下文。
}
~~~

### 上下文组装（Context Assembly）

上下文组装负责把用户问题、会话历史和检索结果整理成模型输入；不负责查询数据库和保存最终消息。

~~~go
type ContextInput struct {
    Question string
    History []MessageContext
    SearchHits []SearchHitContext
}

type ContextPacket struct {
    SystemPrompt string
    Messages []MessageContext
    Sources []SearchHitContext
}

type ContextAssembler interface {
    Build(input ContextInput) (ContextPacket, error) // 生成本轮模型调用所需的上下文。
}
~~~

### 问题改写（Question Rewrite）

问题改写负责把依赖上下文的用户问题整理为可检索问题；不负责执行检索和生成最终回答。

~~~go
type RewriteInput struct {
    Question string
    History []MessageContext
}

type RewrittenQuestion struct {
    Text string
    Keywords []string
}

type QuestionRewriter interface {
    Rewrite(input RewriteInput) (RewrittenQuestion, error) // 根据会话上下文生成检索问题。
}
~~~

### 检索编排（Retrieval Orchestration）

检索编排负责决定是否检索、使用什么检索参数和如何合并结果；不保存文档，也不复制 documents 的检索实现。

~~~go
type RetrievalPlan struct {
    Query string
    Mode string // keyword、full_text、vector、hybrid。
    Limit int
}

type RetrievalOrchestrator interface {
    Retrieve(plan RetrievalPlan, userID string) ([]SearchHitContext, error) // 通过检索 Port 获取本轮知识上下文。
}
~~~

### 工具适配（Tool Adapter）

工具适配负责工具定义、参数、权限和结果转换。Agent 决定调用什么工具，ToolAdapter 通过 Port 调用 documents；工具不保存文档，也不实现文档业务。

~~~go
type ToolDefinition struct {
    Name string
    Description string
    Permission string // read、write 或其他受控能力。
}

type ToolCall struct {
    Name string
    Arguments json.RawMessage
}

type ToolResult struct {
    Success bool
    Data json.RawMessage
    ErrorMessage string
}

type DocumentSearchInput struct {
    UserID string
    Query string
    Mode string
    TopicID string
    Tag string
    Limit int
}

type DocumentSearchPort interface {
    Search(input DocumentSearchInput) ([]SearchHitContext, error) // 调用 documents 的知识检索能力。
}

type ToolPorts struct {
    DocumentSearch DocumentSearchPort
}

type ToolAdapter interface {
    Definitions() []ToolDefinition // 返回本次 Agent 可以使用的工具定义。
    Execute(call ToolCall, ports ToolPorts) (ToolResult, error) // 校验工具调用并通过 Port 执行。
}
~~~

工具调用关系固定为：

~~~text
Agent / agent/rag
  ↓
ToolAdapter
  ↓
DocumentSearchPort
  ↓
documents
~~~

### 回答与引用（Answer & Citation）

回答与引用负责把模型输出整理为带来源的回答结果；不负责把引用对象长期保存到 sessions。

~~~go
type AnswerDraft struct {
    Text string
    SourceHits []SearchHitContext
}

type Citation struct {
    DocumentID string
    DocumentVersionID string
    SourceSnapshot string
    Quote string
}

type AnswerResult struct {
    Text string
    Citations []Citation
    EvidenceStatus string // sufficient、insufficient、failed。
}

type AnswerGenerator interface {
    Generate(context ContextPacket) (AnswerResult, error) // 使用上下文生成回答并选择引用。
    GenerateInsufficientEvidence() AnswerResult // 返回知识库证据不足的结构化结果。
}
~~~

### 运行控制（Run Control）

运行控制负责创建 Run、记录过程事件、取消、继续和按事件序号恢复；不负责拥有 Session 和 Message 的业务数据。

~~~go
type Run struct {
    ID string
    SessionID string
    Status string // queued、running、paused、cancelled、completed、failed。
    LastEventSeq int64
}

type RunEvent struct {
    ID string
    RunID string
    EventSeq int64
    EventType string
    Payload string
    CreatedAt time.Time
}

type RunControl interface {
    Start(sessionID string, question string) (Run, error) // 创建并启动一次问答运行。
    Cancel(runID string) error // 请求取消正在运行的任务。
    Continue(runID string) (Run, error) // 继续可恢复的运行。
    ReadEvents(runID string, afterSeq int64) ([]RunEvent, error) // 按序号读取断线后缺失的过程事件。
}
~~~

过程事件、取消、继续和重连恢复统一属于 Agent 的运行控制，不放入 sessions。

## 流程

~~~text
// 用户发送问题
RunControl.Start(...)
QuestionRewriter.Rewrite(...)
RetrievalOrchestrator.Retrieve(...)
RAGPipeline.AssessEvidence(...)

// 证据足够时生成回答
ContextAssembler.Build(...)
AnswerGenerator.Generate(...)

// 证据不足时返回结构化结果
AnswerGenerator.GenerateInsufficientEvidence(...)

// 需要调用文档工具时
ToolAdapter.Definitions(...)
ToolAdapter.Execute(...)
DocumentSearchPort.Search(...)

// 用户取消或继续
RunControl.Cancel(...)
RunControl.Continue(...)

// 用户断线后重连
RunControl.ReadEvents(runID, afterSeq)

// 运行完成后交给会话模块保存
SessionMessageWriter.SaveAnswer(...)
CitationWriter.Save(...)
~~~
