# 文档管理模块（Documents）

## 功能职责

文档管理模块负责把用户资料转化为可组织、可维护、可检索的知识内容。

- 接收普通笔记、Markdown、网页链接和上传文件。
- 单个录入和批量录入文档。
- 查看批量录入进度，并重试失败的条目。
- 展示已录入文档列表、详情和处理状态。
- 编辑或改写文档，并保留历史版本。
- 管理专题、标签、收藏、文档关联、来源地址和来源快照。
- 归档、恢复和删除文档。
- 对最新文档版本执行切分、全文索引和向量索引刷新。
- 对外提供关键词、全文、向量和混合检索能力。
- 导出用户自己的资料。

## 边界

- 文档、专题、标签、收藏、归档、关联、来源、版本和索引状态归 documents 所有。
- 只接收当前用户身份，不自行判断身份来源。
- 文档能力只通过检索对外提供，不参与调用方如何使用检索结果。
- 只保存文件内容和来源快照，文档与专题的业务关系不随文件一起存放。
- 编辑不会覆盖历史版本；最新版本用于检索，旧版本用于追溯和引用回放。
- 归档改变文档的可见和检索状态，但不删除历史版本和已保存的引用快照。
- 删除文档会清除正文和索引，但已经产生的回答引用仍能打开当时的来源快照。
- 删除专题只解除归类，删除标签只解除标记，都不删除文档本身。
- 批量录入中单条失败不阻塞同批次其他条目，失败条目可以单独重试。

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
    IndexStatus string // 最新版本对应的索引状态，取值与 RefreshStatus.Status 一致。
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
    Delete(documentID string, userID string) error // 删除文档及其索引内容。
}
~~~

编辑、改写或重新导入都会生成新的 DocumentVersion，旧版本保留；回答引用始终指向当时的那一版。

### 知识组织（Knowledge Organization）

知识组织负责专题、标签、收藏和文档之间的关联；不负责文档正文版本和索引算法。

~~~go
type TopicInput struct {
    Name string
    Description string
}

type Topic struct {
    ID string
    UserID string
    Name string
    Description string
}

type Tag struct {
    ID string
    UserID string
    Name string
}

type DocumentRelation struct {
    ID string
    UserID string
    SourceDocumentID string
    TargetDocumentID string
    RelationType string
    CreatedAt time.Time
}

type RelationInput struct {
    UserID string
    SourceDocumentID string
    TargetDocumentID string
    RelationType string
}

type KnowledgeOrganization interface {
    CreateTopic(userID string, input TopicInput) (Topic, error) // 创建当前用户的专题。
    ListTopics(userID string) ([]Topic, error) // 查看当前用户的专题。
    UpdateTopic(userID string, topicID string, input TopicInput) (Topic, error) // 修改专题信息。
    DeleteTopic(userID string, topicID string) error // 删除专题并解除文档归类。
    CreateTag(userID string, name string) (Tag, error) // 新建当前用户的标签。
    ListTags(userID string) ([]Tag, error) // 查看当前用户的标签。
    RenameTag(userID string, tagID string, name string) (Tag, error) // 修改标签名称。
    DeleteTag(userID string, tagID string) error // 删除标签并解除文档上的标记。
    AttachTag(documentID string, tagID string, userID string) error // 给文档打标签。
    DetachTag(documentID string, tagID string, userID string) error // 取消文档上的标签。
    SetFavorite(documentID string, userID string, favorite bool) error // 设置或取消文档收藏。
    CreateRelation(input RelationInput) (DocumentRelation, error) // 建立文档关联。
    ListRelations(documentID string, userID string) ([]DocumentRelation, error) // 查看文档关联。
    DeleteRelation(relationID string, userID string) error // 解除文档关联。
}
~~~

### 来源管理（Source Management）

来源管理负责记录资料来源和来源快照；不负责自动替代用户修改文档业务数据。

~~~go
type SourceInput struct {
    DocumentID string
    SourceType string
    SourceURL string
    Title string
}

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

type DocumentIndexPort interface {
    Refresh(input RefreshRequest) error // 对指定文档版本执行切分和索引刷新。
    GetRefreshStatus(documentID string, userID string) (RefreshStatus, error) // 查询文档索引刷新状态。
}
~~~

刷新按最新版本执行：先写入 queued 状态，异步执行后更新为 processing、ready 或 failed，失败可重试；刷新状态以持久化数据为准。

### 检索（Search）

检索负责按当前用户范围召回匹配的知识片段；不负责切分内容、刷新索引和生成回答。

~~~go
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
    Search(query SearchQuery) ([]SearchHit, error) // 按当前用户范围执行知识检索。
}
~~~

### 导出（Export）

导出负责把当前用户筛选范围内的资料导出成文件；不负责导入，也不负责修改文档。

~~~go
type ExportRequest struct {
    UserID string
    TopicID string
    Tag string
    Format string // markdown、json。
}

type ExportResult struct {
    FileName string
    Content []byte
}

type Exporter interface {
    Export(input ExportRequest) (ExportResult, error) // 按筛选范围导出当前用户的资料。
}
~~~

## 流程

用户把资料录进知识库，之后查看、编辑、整理并检索这些资料。

~~~text
// 单个录入
SingleImporter.Import(...)
SourceManager.CaptureSource(...)
DocumentEditor.Get(...)
DocumentIndexPort.Refresh(...)

// 批量录入
BatchImporter.CreateJob(...)
BatchImporter.GetJob(...)
DocumentIndexPort.Refresh(...)

// 查看批量结果和重试失败条目
BatchImporter.GetJob(...)
BatchImporter.RetryFailed(...)

// 展示和筛选文档
DocumentEditor.List(...)
DocumentEditor.Get(...)
SourceManager.GetSource(...)

// 整理专题和标签
KnowledgeOrganization.CreateTopic(...)
KnowledgeOrganization.ListTopics(...)
KnowledgeOrganization.UpdateTopic(...)
KnowledgeOrganization.DeleteTopic(...)
KnowledgeOrganization.CreateTag(...)
KnowledgeOrganization.ListTags(...)
KnowledgeOrganization.RenameTag(...)
KnowledgeOrganization.DeleteTag(...)

// 编辑或改写文档
DocumentEditor.Update(...)
DocumentEditor.ListVersions(...)
DocumentIndexPort.Refresh(...)

// 收藏、打标、归档和关联
KnowledgeOrganization.SetFavorite(...)
KnowledgeOrganization.AttachTag(...)
KnowledgeOrganization.DetachTag(...)
DocumentEditor.Archive(...)
DocumentEditor.Restore(...)
KnowledgeOrganization.CreateRelation(...)
KnowledgeOrganization.ListRelations(...)
KnowledgeOrganization.DeleteRelation(...)

// 删除文档
DocumentEditor.Delete(...)

// 查询索引状态
DocumentIndexPort.GetRefreshStatus(...)

// 用户检索知识
DocumentSearchPort.Search(...)

// 用户导出资料
Exporter.Export(...)
~~~
