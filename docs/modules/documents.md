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
- 接收认证入口提供的可信身份，校验文档、专题、标签、关联对象及导出范围的归属，不允许模型或请求正文覆盖身份。
- 文档管理通过本模块入口对外提供；Agent 只使用 DocumentSearchPort 检索和复核证据，不访问文档内部数据。
- 只保存文件内容和来源快照，文档与专题的业务关系不随文件一起存放。
- 编辑不会覆盖历史版本；最新版本用于检索，旧版本用于追溯和引用回放。
- 归档改变文档的可见和检索状态，但不删除历史版本和已保存的引用快照。
- 删除文档清除正文、历史版本及索引；已产生的回答仅保留引用摘录、标题、原网址和版本标识，显示“原文已删除”，正文不可访问。
- 删除专题只解除归类，删除标签只解除标记，都不删除文档本身。
- 批量录入中单条失败不阻塞其他条目；按任务与条目序号幂等，录入成功但索引失败只重试索引，不重复创建文档。

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

批量录入负责接收多条资料、记录批量任务和逐条处理结果；处理范围限于文档录入，不执行问答或会话操作。

~~~go
type BatchImportInput struct {
    UserID string
    Items []SingleImportInput // 条目身份统一使用批次身份，不接受不同用户。
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
    SourceSnapshot SourceSnapshot
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
    Update(documentID string, userID string, input DocumentUpdateInput) (DocumentVersion, error) // 编辑文档，原子保存新版本与待索引状态并触发刷新。
    GetVersion(documentID string, versionID string, userID string) (DocumentVersion, error) // 校验归属后读取引用对应版本，文档已删除则返回原文已删除。
    ListVersions(documentID string, userID string) ([]DocumentVersion, error) // 查看文档历史版本。
    Archive(documentID string, userID string) error // 归档文档并更新可见状态。
    Restore(documentID string, userID string) error // 恢复已归档文档。
    Delete(documentID string, userID string) error // 删除文档及其索引内容。
}
~~~

编辑、改写或重新导入都会生成新的 DocumentVersion，旧版本保留；回答引用绑定生成回答时使用的文档版本。

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

来源管理负责记录资料来源和来源快照；文档正文与组织关系由对应的编辑和组织功能维护。

来源正文与 DocumentVersion 一同保留，不随每条 SearchHit 返回；Agent 仅接收选中片段、标题、网址和版本标识。

~~~go
type SourceInput struct {
    UserID string
    DocumentID string
    VersionID string
    Content string
    SourceType string
    SourceURL string
    Title string
}

type SourceSnapshot struct {
    VersionID string
    Content string // 导入时捕获的来源正文，随文档版本保留和删除。
    SourceType string
    SourceURL string
    Title string
    CapturedAt time.Time
}

type SourceManager interface {
    CaptureSource(input SourceInput) (SourceSnapshot, error) // 仅由本模块录入或编辑调用，随对应版本幂等保存来源快照。
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
    Refresh(input RefreshRequest) error // 内部任务对指定版本幂等切分和索引，旧任务不得覆盖当前版本。
    GetRefreshStatus(documentID string, userID string) (RefreshStatus, error) // 查询文档索引刷新状态。
}
~~~

每个任务绑定 DocumentID + VersionID，按该键幂等执行；只有任务版本仍为当前版本时才能发布索引和更新当前状态，旧任务不得覆盖新版本。版本写入与 queued 状态同事务保存，投递失败由定期扫描补投；新版本未 ready 时不回退旧索引。删除、归档立即影响查询过滤，不依赖异步清理完成。

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
    ChunkID string
    SourceURL string
    Score float64
}

type DocumentSearchPort interface {
    Search(query SearchQuery) ([]SearchHit, error) // 过滤归属、归档与当前 ready 版本后召回、去重并融合候选。
    ValidateSources(userID string, hits []SearchHit) ([]SearchHit, error) // 从持久化内容复核片段及当前 ready 版本，排除删除、归档和过期候选，不信任传入正文。
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
// 单个录入，Import 内部保存版本与来源并触发索引
SingleImporter.Import(...)
DocumentEditor.Get(...)

// 批量录入
BatchImporter.CreateJob(...)
BatchImporter.GetJob(...)

// 查看批量结果和重试失败条目
BatchImporter.GetJob(...)
BatchImporter.RetryFailed(...)

// 展示和筛选文档
DocumentEditor.List(...)
DocumentEditor.Get(...)
SourceManager.GetSource(...)

// 从历史引用查看具体版本
DocumentEditor.GetVersion(...)

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
