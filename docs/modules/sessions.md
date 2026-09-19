# 会话模块（Sessions）

## 功能职责

会话模块负责保存用户与知识库之间的对话记录，让用户能够查看、命名、回放和引用历史回答。

- 创建和查询用户会话。
- 保存用户消息和系统回答。
- 修改会话名称。
- 删除会话。
- 保存回答引用和来源快照。
- 按用户范围回放历史消息与引用。

## 边界

- 会话数据以 Session 和 Message 为主体；回答引用挂在某条回答消息上，不单独存在。
- Session 可以保存当前活动 Run 的标识，用于把会话和 Agent 的一次运行关联起来；Run 本身及其生命周期归 Agent 所有。
- 会话模块只保存对话数据，不参与回答是怎么产生的。
- 过程事件不落入会话数据；取消、继续和重连不在这里处理。
- 删除会话时只删除自己的会话数据；应用协调流程随后调用 Agent 按会话清理运行记录，本模块不跨模块删除。
- 引用只保存回答与来源版本的关联，不复制来源正文和索引内容。
- 会话名称由用户自行命名，本模块不做命名推断。

## 内部拆分

### 会话管理（Session Management）

会话管理负责创建、查询、改名、删除和归属校验；不负责回答策略和运行状态。

~~~go
type Session struct {
    ID string
    UserID string
    Name string
    ActiveRunID *string
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
    Delete(sessionID string, userID string) error // 删除会话及其消息。
    ClaimActiveRun(sessionID string, userID string, runID string) error // 原子条件关联活动 Run；已有活动 Run 时拒绝重复领取。
    ClearActiveRun(sessionID string, userID string, runID string) error // 仅清除当前关联的活动 Run。
}
~~~

### 消息历史（Message History）

消息历史负责保存用户问题和系统回答；不负责执行模型调用，也不负责保存运行过程事件。

~~~go
type Message struct {
    ID string
    SessionID string
    Role string // user、assistant。
    Content string
    CreatedAt time.Time
}

type MessageHistory interface {
    Append(message Message) error // 保存一条会话消息。
    List(sessionID string, userID string) ([]Message, error) // 按会话顺序读取历史消息。
}
~~~

### 引用回放（Citation Replay）

引用回放负责保存回答引用及来源快照，让用户可以从历史回答回到具体文档版本；不负责重新检索和生成引用。

~~~go
type Citation struct {
    ID string
    MessageID string
    DocumentID string
    DocumentVersionID string
    SourceSnapshot string
    Quote string
}

type CitationReplay interface {
    Attach(messageID string, citations []Citation) error // 保存回答与来源之间的引用关系。
    List(messageID string, userID string) ([]Citation, error) // 读取回答的引用和来源快照。
}
~~~

## 流程

用户创建会话、提问、改名或删除会话，之后回看历史消息和回答引用。跨模块的提问流程由 `apps/api/app/application` 组合：sessions 保存消息并维护活动 Run 标识，agent 创建和推进 Run；sessions 不启动、取消或恢复 Run。活动 Run 只能通过原子条件更新领取，避免同一会话并发启动多轮运行。

~~~text
// 用户创建会话
SessionManagement.Create(...)

// 保存用户问题
MessageHistory.Append(...)

// 关联本轮 Agent 运行
SessionManagement.ClaimActiveRun(...)

// 系统回答完成后保存消息和引用
MessageHistory.Append(...)
CitationReplay.Attach(...)
SessionManagement.ClearActiveRun(...)

// 取消、失败或不可恢复时也执行同样的清理
SessionManagement.ClearActiveRun(...)

// 用户修改会话名称
SessionManagement.Rename(...)

// 用户删除会话
// 应用协调层先调用 Agent 清理该会话的运行记录
RunControl.DeleteRunsBySession(...)
SessionManagement.Delete(...)

// 用户查看历史
SessionManagement.List(...)
SessionManagement.Get(...)
MessageHistory.List(...)
CitationReplay.List(...)
~~~
