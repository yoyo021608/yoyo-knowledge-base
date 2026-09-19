# 基础设施模块（Infrastructure）

## 功能职责

基础设施模块负责为业务模块提供稳定的数据库、缓存、文件和后台任务能力，不承载个人知识库的业务规则。模型、Embedding、向量库和 MCP 等外部服务连接归 `clients`。

- 提供 PostgreSQL 连接、事务和基础资源生命周期。
- 提供 Redis 缓存和可重试后台任务。
- 保存和读取上传文件及来源快照。
- 读取并校验运行所需的模型服务配置。
- 统一处理连接超时、资源释放和基础错误。

## 边界

- 只提供基础资源访问，不判断任何业务动作是否应该发生。
- 数据库入口不包装成承载所有业务规则的万能 Store。
- 缓存和任务系统不能成为核心数据唯一来源，重要状态必须能从核心存储恢复。
- 只提供模型服务的配置，不参与提示词、模型选择和调用编排；外部服务连接由 `clients` 负责。
- 文件存储只保存字节内容，业务对象的元数据由所属领域自己保存。

## 内部拆分

### 数据持久化（Persistence）

数据持久化负责提供数据库连接和事务生命周期；不决定任何业务对象的创建、更新和状态流转。业务查询贴近所属领域，不通过通用 Store 统一包装。

~~~go
type DatabaseConfig struct {
    URL string
    MaxConnections int
    ConnectionTimeout time.Duration
}

type DatabaseSession struct {
    ID string
    OpenedAt time.Time
}

type Transaction struct {
    ID string
    SessionID string
}

func OpenDatabase(config DatabaseConfig) (DatabaseSession, error) // 打开数据库连接并检查连接状态。
func BeginTransaction(session DatabaseSession) (Transaction, error) // 开始一个数据库事务。
func CommitTransaction(transaction Transaction) error // 提交当前事务中的数据库变化。
func RollbackTransaction(transaction Transaction) error // 回滚当前事务中的数据库变化。
func CloseDatabase(session DatabaseSession) error // 关闭数据库连接并释放资源。
~~~

### 缓存与任务（Cache & Jobs）

缓存与任务负责保存可重建的短期数据和投递后台任务；不负责决定文档版本和问答结果的最终状态。

~~~go
type CacheEntry struct {
    Key string
    Value string
    ExpiresAt *time.Time
}

type Job struct {
    ID string
    Kind string
    Payload string
    Status string // queued、running、success、failed。
}

type CacheJobs interface {
    Get(key string) (CacheEntry, error) // 读取未过期的缓存数据。
    Set(entry CacheEntry) error // 写入带有效期的缓存数据。
    Enqueue(job Job) (string, error) // 投递一个可重试的后台任务。
    Claim(jobID string) (Job, error) // 领取一个待处理的后台任务。
}
~~~

### 文件与来源存储（File & Source Storage）

文件与来源存储负责保存上传文件和来源快照的二进制或文本内容；不负责决定文档归属、版本关系和检索状态。

~~~go
type FileObject struct {
    ID string
    Name string
    ContentType string
    Size int64
    Checksum string
    CreatedAt time.Time
}

type FileStorage interface {
    Put(name string, content []byte, contentType string) (FileObject, error) // 保存文件内容并返回文件描述。
    Get(fileID string) ([]byte, FileObject, error) // 读取文件内容和文件描述。
    Delete(fileID string) error // 删除不再被业务引用的文件内容。
}
~~~

### 模型配置（Model Configuration）

模型配置负责从运行环境读取并校验模型服务调用所需的配置；不负责设计提示词、检索编排、回答生成或保存回答。

~~~go
type ModelConfig struct {
    Provider string // fake、openai 或其他 OpenAI 兼容服务。
    BaseURL string
    APIKey string
    ChatModel string
    EmbeddingModel string
}

func LoadModelConfig() (ModelConfig, error) // 从运行环境读取模型配置并返回配置结果。
func ValidateModelConfig(config ModelConfig) error // 检查当前模型配置是否满足运行要求。
~~~

## 流程

基础设施不直接面向用户；业务模块通过它访问数据库、缓存、文件存储和后台任务，服务启动时建立连接，关闭时释放资源。

~~~text
// 启动服务
OpenDatabase(...)
LoadModelConfig(...)
ValidateModelConfig(...)

// 保存业务数据
BeginTransaction(...)
CommitTransaction(...)

// 投递文档索引刷新任务
CacheJobs.Enqueue(...)
CacheJobs.Claim(...)

// 保存上传文件或来源快照
FileStorage.Put(...)
FileStorage.Get(...)

// 服务关闭
CloseDatabase(...)
~~~
