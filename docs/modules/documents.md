# 文档管理模块（Documents）

## 功能职责

文档管理模块负责把用户资料转化为可组织、可维护、可检索的知识内容。

- 接收普通笔记、Markdown、网页链接和上传文件。
- 单个录入和批量录入文档。
- 展示已录入文档列表、详情和处理状态。
- 编辑或改写文档，并保留历史版本。
- 管理专题、标签、收藏、归档、文档关联、来源地址和来源快照。
- 对最新文档版本执行切分、全文索引和向量索引刷新。
- 为 Agent 提供关键词、全文、向量和混合检索能力。

## 边界

- 文档、专题、标签、收藏、归档、关联、来源、版本和索引状态归 documents 所有。
- documents 不负责用户注册、登录和会话身份签发，只接收当前用户身份。
- documents 不负责回答生成、问题改写和 Agent 运行控制；Agent 只能通过检索 Port 使用文档能力。
- 文件存储只保存文件内容或来源快照，文档与专题的业务关系仍由 documents 管理。
- 编辑不会覆盖历史版本；最新版本用于检索，旧版本用于追溯和引用回放。
- 归档改变文档的可见和检索状态，但不删除历史版本和已保存的引用快照。
- Redis 可以承载索引刷新任务，但不能作为文档和版本的唯一数据源。

## 内部拆分

### 单个录入（Single Import）

单个录入负责校验一条资料、建立文档和首个版本，并投递索引刷新；不负责回答问题。

~~~go
type SingleImportInput struct {
    UserID string
    Title string
    Content string
    SourceType string // note、markdown、web、file。
    SourceURL string
    TopicID string
    Tags []string
}

type ImportResult struct {
    DocumentID string
    VersionID string
    IndexStatus string // queued、processing、ready、failed。
}

type SingleImporter interface {
    Import(input SingleImportInput) (ImportResult, error) // 保存单条资料并启动索引刷新。
}
~~~

### 批量录入（Batch Import）

批量录入负责接收多条资料、记录批量任务和逐条处理结果；不负责把批量逻辑扩散到其他领域。

~~~go
type BatchImportInput struct {
    UserID string
    Items []SingleImportInput
}

type ImportJob struct {
    ID string
    UserID string
    Mode string // single、batch。
    Status string // queued、running、completed、partial、failed。
    TotalCount int
    SuccessCount int
    FailureCount int
}

type ImportItemResult struct {
    ID string
    JobID string
    InputIndex int
    Status string // success、failed。
    DocumentID string
    ErrorMessage string
}

type BatchImporter interface {
    CreateJob(input BatchImportInput) (ImportJob, error) // 创建批量录入任务并保存任务状态。
    GetJob(jobID string, userID string) (ImportJob, []ImportItemResult, error) // 查看批量任务及逐条处理结果。
    RetryFailed(jobID string, userID string) (ImportJob, error) // 只重试失败条目并更新任务状态。
}
~~~

### 文档与版本（Document & Version）

文档与版本负责文档当前状态、历史版本、来源快照和编辑；不负责执行模型问答。

~~~go
type Document struct {
    ID string
    UserID string
    TopicID string
    Title string
    Status string // active、archived。
    IsFavorite bool
    CurrentVersion int
    IndexStatus string // queued、processing、ready、failed。
    UpdatedAt time.Time
}

type DocumentVersion struct {
    ID string
    DocumentID string
    Version int
    TitleSnapshot string
    ContentSnapshot string
    SourceSnapshot string
    CreatedAt time.Time
}

type DocumentUpdateInput struct {
    Title string
    Content string
    TopicID string
    Tags []string
    SourceURL string
}

type DocumentFilter struct {
    Keyword string
    TopicID string
    Tag string
    SourceType string
    IndexStatus string
    Status string
    IsFavorite *bool
}

type DocumentEditor interface {
    Get(documentID string, userID string) (Document, error) // 获取当前用户可访问的文档。
    List(userID string, filter DocumentFilter) ([]Document, error) // 展示当前用户的文档列表。
    Update(documentID string, userID string, input DocumentUpdateInput) (DocumentVersion, error) // 编辑文档并创建新版本。
    ListVersions(documentID string, userID string) ([]DocumentVersion, error) // 查看文档历史版本。
    Archive(documentID string, userID string) error // 归档文档并更新可见状态。
    Restore(documentID string, userID string) error // 恢复已归档文档。
}
~~~

### 知识组织（Knowledge Organization）

知识组织负责专题、标签、收藏和文档之间的关联；不负责文档正文版本和索引算法。

~~~go
type Topic struct {
    ID string
    UserID string
    Name string
    Description string
}

type DocumentRelation struct {
    ID string
    UserID string
    SourceDocumentID string
    TargetDocumentID string
    RelationType string
    CreatedAt time.Time
}

type TopicOrganization interface {
    CreateTopic(userID string, input TopicInput) (Topic, error) // 创建当前用户的专题。
    ListTopics(userID string) ([]Topic, error) // 查看当前用户的专题。
    UpdateTopic(userID string, topicID string, input TopicInput) (Topic, error) // 修改专题信息。
    SetFavorite(documentID string, userID string, favorite bool) error // 设置或取消文档收藏。
    CreateRelation(input RelationInput) (DocumentRelation, error) // 建立文档关联。
    ListRelations(documentID string, userID string) ([]DocumentRelation, error) // 查看文档关联。
    DeleteRelation(relationID string, userID string) error // 解除文档关联。
}
~~~

### 来源管理（Source Management）

来源管理负责记录资料来源和来源快照；不负责自动替代用户修改文档业务数据。

~~~go
type SourceSnapshot struct {
    SourceType string
    SourceURL string
    Title string
    CapturedAt time.Time
}

type SourceManager interface {
    CaptureSource(input SourceInput) (SourceSnapshot, error) // 保存文档来源快照。
    GetSource(documentID string, userID string) (SourceSnapshot, error) // 查看文档来源信息。
}
~~~

### 索引刷新（Index Refresh）

索引刷新负责从最新版本生成可检索内容并更新索引；不负责改变文档标题、专题、收藏和版本关系。

~~~go
type RefreshRequest struct {
    DocumentID string
    VersionID string
}

type RefreshStatus struct {
    DocumentID string
    VersionID string
    Status string // queued、processing、ready、failed。
    ErrorMessage string
    UpdatedAt time.Time
}

type SearchQuery struct {
    UserID string
    Text string
    Mode string // keyword、full_text、vector、hybrid。
    TopicID string
    Tag string
    Limit int
}

type SearchHit struct {
    DocumentID string
    VersionID string
    Title string
    ContentSnippet string
    SourceSnapshot string
    Score float64
}

type DocumentSearchPort interface {
    Refresh(input RefreshRequest) error // 对指定文档版本执行切分和索引刷新。
    GetRefreshStatus(documentID string, userID string) (RefreshStatus, error) // 查询文档索引刷新状态。
    Search(query SearchQuery) ([]SearchHit, error) // 按当前用户范围执行知识检索。
}
~~~

## 流程

~~~text
// 单个录入
SingleImporter.Import(...)
DocumentEditor.Get(...)
DocumentSearchPort.Refresh(...)

// 批量录入
BatchImporter.CreateJob(...)
BatchImporter.GetJob(...)
DocumentSearchPort.Refresh(...)

// 查看批量结果和重试失败条目
BatchImporter.GetJob(...)
BatchImporter.RetryFailed(...)

// 展示和筛选文档
DocumentEditor.List(...)
DocumentEditor.Get(...)

// 编辑或改写文档
DocumentEditor.Update(...)
DocumentEditor.ListVersions(...)
DocumentSearchPort.Refresh(...)

// 收藏、归档和关联
TopicOrganization.SetFavorite(...)
DocumentEditor.Archive(...)
DocumentEditor.Restore(...)
TopicOrganization.CreateRelation(...)
TopicOrganization.ListRelations(...)
TopicOrganization.DeleteRelation(...)

// 查询索引状态
DocumentSearchPort.GetRefreshStatus(...)

// Agent 通过 Port 检索知识
DocumentSearchPort.Search(...)
~~~
