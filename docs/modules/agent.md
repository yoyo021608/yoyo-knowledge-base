# Agent 编排模块（Agent Orchestration）

## 功能职责

Agent 编排模块负责把用户问题组织成一轮完整的知识调用过程，产出带来源的回答结果。

- 组装当前问题、会话上下文和检索结果。
- 对问题做改写、检索编排和上下文组装。
- 在需要时调用知识检索能力获取知识片段。
- 一次检索不够时，自己换一组查询再查一次，不把重问推给用户。
- 组织上下文并生成回答，返回带来源引用的结果。
- 判断检索证据是否足够，并规范化回答引用。
- 管理 Run 状态、过程事件、取消、继续和断线重连恢复。

## 边界

- Agent 负责“如何完成一次回答”的编排，不拥有知识内容本身。
- 证据判断只决定证据够不够、要不要再查；知识内容的切分、版本和索引不由 Agent 维护。
- Agent 不直接读取知识内容和索引数据；需要知识时通过检索 Port 或工具适配层调用。
- 工具只定义参数、权限和结果适配，不实现知识内容的加工和检索。
- Agent 只产生回答结果和运行事件，对话记录的保存由应用协调层负责。
- Agent 对外提供模块级的编排能力；应用装配层负责把 HTTP 请求转换为模块调用，不把路由逻辑放进 Agent。
- 过程事件是可回放的运行通知，最终回答、消息和引用仍然以持久化业务数据为准。
- 证据不足时返回明确状态，不把模型推测伪装成知识库结论。

## 内部拆分

### 证据判断（Evidence Assessment）

证据判断负责判断检索结果是否足以支持回答，并在不足时给出下一次要查什么；不负责执行检索、组装上下文和生成回答。

~~~go
type EvidenceDecision struct {
    Sufficient bool
    Reason string
    HitCount int
}

type NextRetrieval struct {
    Retry bool
    Query string // 需要再查时使用的新查询。
}

type RAGPipeline interface {
    AssessEvidence(hits []SearchHitContext) (EvidenceDecision, error) // 判断当前检索结果是否足以支持回答。
    PlanNextRetrieval(decision EvidenceDecision) (NextRetrieval, error) // 证据不足时给出下一次查询。
}
~~~

documents 已经完成权限、文档状态、当前版本和候选去重；Agent 只在返回的候选集上做本轮相关性重排、证据判断和上下文选择。证据不足时只允许有限次改写与重检索，仍不足就返回明确的证据不足结果。

### 上下文组装（Context Assembly）

上下文组装负责把用户问题、会话历史和检索结果整理成模型输入；不负责读取历史数据和保存最终消息。

~~~go
type MessageContext struct {
    Role string // user、assistant。
    Content string
}

type SearchHitContext struct {
    DocumentID string
    VersionID string
    Title string
    ContentSnippet string
    Score float64
}

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

上下文组装使用固定的 token 预算，优先保留高分且能够形成引用的片段；内容过长时压缩或分批摘要，不能无限增加检索结果数量。

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

检索编排负责把要查的问题变成检索参数，并决定本轮是否需要再次请求 documents；不负责实现召回、候选合并、文档过滤和索引，也不判断最终回答是否已经生成。

~~~go
type RetrievalPlan struct {
    Query string
    Mode string // keyword、full_text、vector、hybrid。
    Limit int
}

type RetrievalOrchestrator interface {
    PlanRetrieval(question string, userID string) (RetrievalPlan, error) // 把要查的问题整理成本轮检索参数。
    Retrieve(plan RetrievalPlan, userID string) ([]SearchHitContext, error) // 通过 DocumentSearchPort 获取有限候选集。
}
~~~

### 工具适配（Tool Adapter）

工具适配负责工具定义、参数、权限和结果转换。Agent 决定调用什么工具，ToolAdapter 直接使用 documents 的 `DocumentSearchPort` 调用知识检索，不另外定义第二个检索端口；工具不保存文档，也不实现文档业务，检索结果由 Agent 侧转换为内部使用的 `SearchHitContext`。

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

type ToolPorts struct {
    DocumentSearch DocumentSearchPort
}

type ToolAdapter interface {
    Definitions() []ToolDefinition // 返回本次 Agent 可以使用的工具定义。
    Handle(call ToolCall, ports ToolPorts) (ToolResult, error) // 校验工具调用并通过 Port 处理。
}
~~~

### 回答与引用（Answer & Citation）

回答与引用负责把模型输出整理为带来源的回答结果；不负责把引用对象长期保存到 sessions。

~~~go
type AnswerDraft struct {
    Text string
    SourceHits []SearchHitContext
}

type AnswerCitation struct {
    DocumentID string
    DocumentVersionID string
    SourceSnapshot string
    Quote string
}

type AnswerResult struct {
    Text string
    Citations []AnswerCitation
    EvidenceStatus string // sufficient、insufficient、failed。
}

type AnswerGenerator interface {
    Generate(context ContextPacket) (AnswerResult, error) // 使用上下文生成回答并选择引用。
    GenerateInsufficientEvidence() AnswerResult // 返回知识库证据不足的结构化结果。
}
~~~

### 运行控制（Run Control）

运行控制负责创建 Run、记录过程事件、取消、继续和按事件序号恢复；不负责拥有 Session、Message 和 Citation 的业务数据。Session 只保存当前活动 Run 的关联标识。

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

type RunSnapshot struct {
    RunID string
    Step string
    InputSummary string
    RetrievalPlan string
    SelectedEvidence []string
    RetryCount int
    NextStep string
}

type RunControl interface {
    Start(sessionID string, question string) (Run, error) // 创建 queued Run；应用协调层关联成功后才开始执行。
    Cancel(runID string) error // 请求取消正在运行的任务。
    Continue(runID string) (Run, error) // 继续可恢复的运行。
    ReadEvents(runID string, afterSeq int64) ([]RunEvent, error) // 按序号读取断线后缺失的过程事件。
    DeleteRunsBySession(sessionID string, userID string) error // 由应用协调流程调用，清理该会话的运行记录。
    Discard(runID string, userID string) error // 活动 Run 关联失败时清理尚未执行的 Run。
}
~~~

过程事件、取消、继续和重连恢复统一属于 Agent 的运行控制。每个关键步骤先保存 RunSnapshot，再记录 RunEvent 并作为通知推送；进程重启从快照恢复，客户端断线后按 `event_seq` 回放，内存里的临时状态不作为事实来源。模型或检索能力失败时保留已完成步骤、失败原因和重试次数，不可恢复时返回明确的失败状态。

恢复时以快照和已保存的步骤结果为准：已经完成的步骤不重复产生回答或引用，未完成的步骤从最近快照继续。只有可重试的外部失败才进行有限重试，超过次数或遇到不可重试错误就保留失败原因并结束本次运行。

## 流程

用户提问后由 `apps/api/app/application` 先保存用户消息，再请求 Agent 创建 queued Run；sessions 原子领取活动 Run 后，Agent 才开始执行。若领取失败，应用协调层调用 Agent 清理未执行的 Run。回答完成后由应用协调层调用 sessions 保存回答和 Citation。Run 被取消或失败时，也必须清理活动 Run 关联；证据不足时返回明确的结构化结果，过程中用户可以继续，断线后可以重连补回过程事件。

~~~text
// application 协调用例保存用户问题并创建尚未执行的 Run
MessageHistory.Append(...)
RunControl.Start(...)
SessionManagement.ClaimActiveRun(...)
// ClaimActiveRun 失败时：
RunControl.Discard(...)
QuestionRewriter.Rewrite(...)
RetrievalOrchestrator.PlanRetrieval(...)
RetrievalOrchestrator.Retrieve(...)
RAGPipeline.AssessEvidence(...)
ContextAssembler.Build(...)
AnswerGenerator.Generate(...)

// 应用协调层保存回答和引用，并清理活动 Run 关联
MessageHistory.Append(...)
CitationReplay.Attach(...)
SessionManagement.ClearActiveRun(...)

// 一次没查够时再查一次
RAGPipeline.PlanNextRetrieval(...)
RetrievalOrchestrator.Retrieve(...)

// 用户取消
RunControl.Cancel(...)

// 用户继续
RunControl.Continue(...)

// 用户断线后重连
RunControl.ReadEvents(...)
~~~
