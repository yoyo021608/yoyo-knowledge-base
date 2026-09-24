# Agent 编排模块（Agent Orchestration）

## 功能职责

Agent 编排模块负责把用户问题组织成一轮完整的知识调用过程，产出带来源的回答结果。

- 组装当前问题、会话上下文和检索结果。
- 对问题做改写、检索编排和上下文组装。
- 在需要时调用知识查询能力获取候选片段，并决定关键词、全文、向量或混合检索如何组合。
- 检索证据不足时自动改写查询，并在预算内补充检索。
- 组织上下文并生成回答，返回带来源引用的结果。
- 判断检索证据是否足够，并规范化回答引用。
- 评估检索命中、证据覆盖和引用是否满足预设标准，为调整检索策略提供结果。
- 管理 Run 状态、过程事件、取消、继续和断线重连恢复。

Agent 根据任务模式选择流程：简单问题走一次检索和回答；复杂问题进入多步研究；选择多份资料时进入对比；指定学习专题时生成练习并分析答案。模式选择只改变编排方式，不改变 documents 的数据归属和 sessions 的结果保存方式。

本模块的直接产出是任务计划、检索候选的处理结果、证据判断、回答草稿、研究报告、对比结论、练习内容和评估结果。它可以请求其他模块提供能力，但不直接写入文档表、索引表或会话消息；最终结果由调用方协调后保存到 sessions。

## 边界

- Agent 负责“如何完成一次回答”的编排，不拥有知识内容本身。
- 证据判断负责评估充分性并确定是否补充检索；知识内容的切分、版本和索引不由 Agent 维护。
- Agent 不直接读取知识内容和索引数据；需要知识时通过检索 Port 或工具适配层调用。
- 工具只定义参数、权限和结果适配，不实现知识内容的加工和检索。
- Agent 只产生回答结果和运行事件，对话记录的保存由调用方负责。
- Agent 负责判断和编排，不拥有文档、知识点、实体、关系或索引；最终回答、引用和用户反馈由 sessions 保存。
- 过程事件是可回放的运行通知，最终回答、消息和引用仍然以持久化业务数据为准。
- 证据不足时返回明确状态，不把模型推测伪装成知识库结论。

## 内部拆分

### 证据判断（Evidence Assessment）

证据判断负责判断检索结果是否足以支持回答，并在证据不足时生成补充查询；不负责执行检索、组装上下文和生成回答。

~~~go
type EvidenceDecision struct {
    Sufficient bool
    Reason string
    HitCount int
    MissingInformation []string
}

type NextRetrieval struct {
    Retry bool
    Query string // 需要再查时使用的新查询。
}

type RAGPipeline interface {
    AssessEvidence(question string, hits []SearchHitContext) (EvidenceDecision, error) // 判断当前检索结果是否足以支持回答。
    PlanNextRetrieval(question string, previousQueries []string, decision EvidenceDecision, attempt int, maxAttempts int) (NextRetrieval, error) // 证据不足时给出下一次查询。
}
~~~

证据判断检查材料是否覆盖当前问题，不能只看命中数量或相似度；默认最多补查 1 次，总检索时间上限 30 秒，均可配置；成功检索后仍缺材料才返回证据不足，检索超时或服务不可用返回可重试故障，不声称知识库没有证据。

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
    ChunkID string
    SourceURL string
    Score float64
}

type ContextBudget struct {
    ModelWindow int
    ReservedOutputTokens int
    SafetyMargin int
    HistoryBudget int
    EvidenceBudget int
}

type ContextInput struct {
    Question string
    History []MessageContext
    SearchHits []SearchHitContext
    Budget ContextBudget
}

type ContextPacket struct {
    SystemPrompt string
    Messages []MessageContext
    Sources []SearchHitContext
    InputTokens int
}

type ContextAssembler interface {
    Build(input ContextInput) (ContextPacket, error) // 生成本轮模型调用所需的上下文。
}
~~~

输入上限为模型窗口减去输出预留和安全余量；先保留系统指令与当前问题，再选近期历史和去重、重排后的证据。历史与证据分别限额，最终按模型 tokenizer 复核；固定内容超限则返回输入过长，不静默截断问题。改写和证据判断的模型调用同样受预算约束；摘要仅用于压缩历史，不覆盖原始消息，检索内容作为不可信资料而非系统指令。

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

检索编排负责制定查询计划，通过注入的 DocumentSearchPort 获取候选，组合不同查询方式并按当前问题重排、去重和选择证据；不实现索引引擎、不维护片段和知识关系，也不保存文档。

~~~go
type RetrievalPlan struct {
    Query string
    Mode string // keyword、full_text、vector、hybrid。
    Limit int
}

type RetrievalOrchestrator interface {
    PlanRetrieval(question string, userID string) (RetrievalPlan, error) // 把要查的问题整理成本轮检索参数。
    Retrieve(plan RetrievalPlan, userID string) ([]SearchHitContext, error) // 调用检索契约并转换、重排候选，不复制召回算法。
}
~~~

### 运行评估（Run Evaluation）

运行评估负责记录一次检索和回答是否达到预设质量标准。它可以检查目标片段是否进入候选、引用是否对应实际证据、证据不足是否被正确拦截，并输出评估结果供后续调整检索计划使用；不修改文档内容，也不代替用户反馈。

```text
评估输入：问题、检索候选、最终引用、回答状态
评估输出：命中情况、引用覆盖情况、证据判断结果、失败原因
```

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

type ToolPorts struct {
    DocumentSearch DocumentSearchPort // 复用文档模块定义的唯一检索契约。
}

type ToolAdapter interface {
    Definitions() []ToolDefinition // 返回本次 Agent 可以使用的工具定义。
    Execute(userID string, call ToolCall, ports ToolPorts) (ToolResult, error) // 使用可信身份校验工具参数并调用检索契约，身份不可由模型覆盖。
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
    ChunkID string
    TitleSnapshot string
    SourceURL string
    Quote string
}

type AnswerResult struct {
    Text string
    Citations []AnswerCitation
    EvidenceStatus string // sufficient、insufficient、failed。
}

type AnswerGenerator interface {
    Generate(context ContextPacket) (AnswerResult, error) // 生成回答，校验引用只来自实际入选证据且摘录能匹配该版本。
    GenerateInsufficientEvidence() AnswerResult // 返回知识库证据不足的结构化结果。
}
~~~

### 运行控制（Run Control）

运行控制负责创建 Run、记录过程事件、取消、继续和按事件序号恢复；不负责拥有 Session 和 Message 的业务数据。

~~~go
type Run struct {
    ID string
    SessionID string
    UserID string
    RequestID string // 同一用户请求的幂等标识。
    Status string // queued、running、paused、finalizing、cancelled、completed、failed。
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
    InputMessageID string
    Input ContextInput // 固定本轮问题、历史与预算，不保存密钥。
    Step string // rewrite、retrieve、generate、persist_answer。
    Queries []string
    SelectedSources []SearchHitContext
    Result *AnswerResult
    ChatModel string
    Attempt int // 重新生成时递增，旧的部分输出标记为中断。
    Revision int64 // 条件更新防止旧执行覆盖新快照。
}

type RunControl interface {
    CreateRun(sessionID string, userID string, requestID string, input ContextInput) (Run, error) // 按用户、会话及 requestID 幂等创建 Run；同键不同问题拒绝，重试复用原历史快照。
    ExecuteRun(runID string, userID string, inputMessageID string) error // 协调方完成会话领取和消息保存后启动运行。
    SaveSnapshot(snapshot RunSnapshot, expectedRevision int64) error // 内部执行者条件保存快照及同一步骤事件。
    LoadSnapshot(runID string, userID string) (RunSnapshot, error) // 校验归属后读取恢复所需数据。
    Cancel(runID string, userID string) error // 校验归属并取消，阻止后续执行与结果提交。
    PauseInterrupted(runID string) error // 仅内部恢复任务将确认无执行者的中断运行转为 paused。
    Continue(runID string, userID string) (Run, error) // 仅继续可恢复的暂停运行，不重启终态运行。
    BeginFinalize(runID string, userID string) error // 有完整结果时条件进入 finalizing，与取消互斥；此后取消返回已在保存。
    Complete(runID string, userID string) error // 最终回答保存成功后幂等完成运行。
    Fail(runID string, userID string, reason string) error // 标记不可恢复或领取失败的运行。
    ReadEvents(runID string, userID string, afterSeq int64, limit int) ([]RunEvent, error) // 校验归属后有界回放过程事件。
    ListRecoverable(limit int) ([]Run, error) // 内部恢复任务扫描非终态和待协调的运行。
    PurgeSessionRuns(sessionID string, userID string) error // 会话停止接收提问后取消并清理运行，禁止迟到写入。
}
~~~

同一 Run 仅允许一个执行者；恢复复用已完成步骤，生成中断则重新生成并标记旧输出失效。快照与对应事件同事务保存，事件回放不触发执行。最终提交与取消互斥，回答持久化成功后才完成 Run；跨模块保存与清理由调用方协调。

生成前复核证据版本与访问状态，失效证据触发预算内重检索；最终提交固定完整结果，不重复生成。来源复核与删除独立提交，删除后的引用按已保存摘录回放。

## 流程

用户提问后由 Agent 组织一轮完整的知识调用并产出带来源的回答结果，记录的保存由调用方负责；证据不足时返回明确的结构化结果，过程中用户可以取消、继续，断线后可以重连补回过程事件。

~~~text
// 用户提问
RunControl.CreateRun(...)
RunControl.ExecuteRun(...)
QuestionRewriter.Rewrite(...)
RetrievalOrchestrator.PlanRetrieval(...)
RetrievalOrchestrator.Retrieve(...)
RAGPipeline.AssessEvidence(...)
ContextAssembler.Build(...)
AnswerGenerator.Generate(...)
RunControl.SaveSnapshot(...)

// 调用方领取最终提交权
DocumentSearchPort.ValidateSources(...)
RunControl.BeginFinalize(...)

// 调用方保存回答成功后完成运行
RunControl.Complete(...)

// 证据不足时补充检索
RAGPipeline.PlanNextRetrieval(...)
RetrievalOrchestrator.Retrieve(...)
RAGPipeline.AssessEvidence(...)

// 用户取消
RunControl.Cancel(...)

// 用户继续
RunControl.LoadSnapshot(...)
DocumentSearchPort.ValidateSources(...)
RunControl.Continue(...)

// 用户断线后重连
RunControl.ReadEvents(...)
~~~
