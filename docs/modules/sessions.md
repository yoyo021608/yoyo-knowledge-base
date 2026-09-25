# 会话模块（Sessions）

## 功能职责

会话模块负责保存用户与知识库之间产生的交互结果，让用户能够查看、命名、回放和引用历史回答，也能保留研究任务、练习记录和反馈。

- 创建和查询用户会话。
- 保存用户消息和系统回答。
- 修改会话名称。
- 删除会话。
- 保存回答引用和来源快照。
- 保存研究任务结果、练习提交、掌握度快照和用户反馈。
- 按用户范围回放历史消息与引用。

## 边界

- 会话数据以 Session 和 Message 为主体；回答引用挂在某条回答消息上，不单独存在。
- 会话模块只保存对话数据，回答生成由 Agent 负责。
- 研究计划、检索过程和练习生成由 Agent 负责；本模块只保存任务结果、提交记录和反馈。
- 过程事件不落入会话数据；取消、继续和重连不在这里处理。
- 引用保留版本标识、摘录、标题和原网址，不复制完整正文或索引；原文删除后仍可看摘录，但提示原文已删除。
- 一个会话同时只接受一个活动 Run；领取失败返回忙碌，不额外保存用户问题，不排队。
- 身份由认证入口传入，本模块检查会话、消息归属；不信任请求正文中的用户标识。
- 删除会话先标记 deleting，拒绝新提问和迟到结果，再由协调方清理 Agent 运行，最后删除消息与引用；中断后可重复完成清理。
- 会话名称由用户自行命名，本模块不做命名推断。

研究任务、对比结果和学习练习都是交互结果的不同形态：研究任务保存问题、状态和最终报告，对比结果保存参与比较的资料及结论，练习记录保存题目、用户答案、判定和掌握度快照。它们的生成策略属于 Agent，保存、查询、回放和反馈属于 sessions。

用户在本模块看到的是会话列表、消息历史、研究报告、对比结果、练习记录、引用回放和反馈入口。sessions 只保存已经产生的交互结果和状态，不负责重新检索、重新生成答案或修改知识库内容。

## 内部拆分

### 会话管理（Session Management）

会话管理负责创建、查询、改名、删除和归属校验；不负责回答策略和运行状态。

~~~go
type Session struct {
    ID string
    UserID string
    Name string
    ActiveRunID *string // 只保存关联，不拥有运行状态。
    Status string // active、deleting。
    CreatedAt time.Time
    UpdatedAt time.Time
}

type SessionInput struct {
    UserID string
    Name string
}

type RenameSessionInput struct {
    SessionID string
    UserID string
    Name string
}

type SessionManagement interface {
    Create(input SessionInput) (Session, error) // 创建属于当前用户的会话。
    List(userID string) ([]Session, error) // 查询当前用户的会话列表。
    Get(sessionID string, userID string) (Session, error) // 获取当前用户可访问的会话。
    Rename(input RenameSessionInput) (Session, error) // 修改当前用户会话名称。
    TryClaimRun(sessionID string, userID string, runID string) error // 仅活动会话且关联为空时原子领取，同一 Run 重试成功。
    ReleaseRun(sessionID string, userID string, runID string) error // 仅释放匹配的关联，重复释放无副作用。
    BeginDelete(sessionID string, userID string) error // 标记删除中，阻止新领取和消息写入。
    ListDeleting(limit int) ([]Session, error) // 内部恢复任务扫描待清理会话，即使运行记录已清除也能继续删除。
    Delete(sessionID string, userID string) error // 运行清理完成后幂等删除会话、消息及引用。
}
~~~

### 消息历史（Message History）

消息历史负责保存用户问题和系统回答；不负责执行模型调用，也不负责保存运行过程事件。

~~~go
type Message struct {
    ID string
    SessionID string
    RunID string // 与 Role 组成会话内唯一键，重试不重复插入。
    Role string // user、assistant。
    Content string
    CreatedAt time.Time
}

type MessageHistory interface {
    AppendUser(userID string, message Message) (Message, error) // 核对活动 Run 后幂等保存用户消息，相同键不同内容拒绝。
    SaveAnswer(userID string, message Message, citations []Citation) (Message, error) // 同一事务保存回答及引用，按 Run 幂等且相同键不同结果拒绝；先检查已存结果，新写入核对活动关联，删除中的会话拒绝。
    List(sessionID string, userID string) ([]Message, error) // 按会话顺序读取历史消息。
}
~~~

### 引用回放（Citation Replay）

引用回放负责读取随回答保存的引用，原文存在时可定位具体版本，原文删除后展示保留的摘录与来源信息；写入统一由消息历史的 SaveAnswer 完成，不重新检索和生成引用。

~~~go
type Citation struct {
    ID string
    MessageID string
    DocumentID string
    DocumentVersionID string
    ChunkID string
    TitleSnapshot string
    SourceURL string
    Quote string // 自包含摘录；版本标识不建立导致删除受阻或引用级联删除的外键。
}

type CitationReplay interface {
    List(messageID string, userID string) ([]Citation, error) // 读取回答的引用和来源快照。
}
~~~

## 流程

用户创建会话、提问、改名或删除会话，之后回看历史消息和回答引用。

~~~text
// 用户创建会话
SessionManagement.Create(...)

// 调用方创建 Run 后领取会话并保存问题
SessionManagement.TryClaimRun(...)
MessageHistory.AppendUser(...)

// 系统回答完成后保存消息和引用
MessageHistory.SaveAnswer(...)

// 调用方完成 Run 后释放关联
SessionManagement.ReleaseRun(...)

// 用户修改会话名称
SessionManagement.Rename(...)

// 用户删除会话，调用方在两步之间完成运行清理
SessionManagement.BeginDelete(...)
SessionManagement.Delete(...)

// 用户查看历史
SessionManagement.List(...)
SessionManagement.Get(...)
MessageHistory.List(...)
CitationReplay.List(...)
~~~
