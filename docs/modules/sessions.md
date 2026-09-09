# 会话模块（Sessions）

## 功能职责

会话模块负责保存用户与知识库之间的对话记录，让用户能够查看、命名、回放和引用历史回答。

- 创建和查询用户会话。
- 保存用户消息和 Agent 回答。
- 修改会话名称。
- 保存回答引用和来源快照。
- 按用户范围回放历史消息与引用。

## 边界

- Session、Message 和 Citation 属于 sessions 模块。
- 会话模块不负责问题改写、文档检索、回答生成和 Agent 运行编排。
- 过程事件、取消、继续和断线重连统一由 agent 的运行控制负责，sessions 不保存 RunEvent。
- 会话引用只保存回答与文档版本之间的关联，不复制 documents 的文档内容和索引实现。
- 会话名称可以由用户修改；自动生成名称如果需要，也只能使用 Agent 返回的结果，不把命名逻辑扩散到其他模块。

## 内部拆分

### 会话管理（Session Management）

会话管理负责创建、查询和归属校验；不负责回答策略和运行状态。

~~~go
type Session struct {
    ID string
    UserID string
    Name string
    Status string // active、archived。
    CreatedAt time.Time
    UpdatedAt time.Time
}

type SessionInput struct {
    UserID string
    Name string
}

type SessionManagement interface {
    Create(input SessionInput) (Session, error) // 创建属于当前用户的会话。
    List(userID string) ([]Session, error) // 查询当前用户的会话列表。
    Get(sessionID string, userID string) (Session, error) // 获取当前用户可访问的会话。
}
~~~

### 消息历史（Message History）

消息历史负责保存用户问题和系统回答；不负责执行模型调用，也不负责保存运行过程事件。

~~~go
type Message struct {
    ID string
    SessionID string
    Role string // user、assistant、system。
    Content string
    CreatedAt time.Time
}

type MessageHistory interface {
    Append(message Message) error // 保存一条会话消息。
    List(sessionID string, userID string) ([]Message, error) // 按会话顺序读取历史消息。
}
~~~

### 会话命名（Session Naming）

会话命名负责修改和读取会话名称；不负责修改消息内容和运行状态。

~~~go
type RenameSessionInput struct {
    SessionID string
    UserID string
    Name string
}

type SessionNaming interface {
    Rename(input RenameSessionInput) (Session, error) // 修改当前用户会话名称。
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

~~~text
// 用户创建会话
SessionManagement.Create(...)

// 保存用户问题
MessageHistory.Append(...)

// Agent 完成回答后保存消息和引用
MessageHistory.Append(...)
CitationReplay.Attach(...)

// 用户修改会话名称
SessionNaming.Rename(...)

// 用户查看历史
SessionManagement.List(...)
SessionManagement.Get(...)
MessageHistory.List(...)
CitationReplay.List(...)
~~~
