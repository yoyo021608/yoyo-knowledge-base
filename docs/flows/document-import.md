# 文档录入流程

```mermaid
flowchart TD
    A[用户提交笔记、Markdown、网页或文件] --> B[controller 获取当前用户]
    B --> C{documents 校验内容和来源}
    C -- 失败 --> D[返回录入错误]
    C -- 通过 --> E[创建 Document 和 DocumentVersion]
    E --> F[保存来源快照]
    F --> G[documents 创建索引刷新任务]
    G --> H[返回 queued 状态]
    H --> I[后台 Worker 领取任务并生成片段]
    I --> J[infra 提供全文和向量索引连接]
    J --> K{索引是否成功}
    K -- 否 --> L[版本标记 failed，可重试]
    K -- 是 --> M[最新版本标记 ready]
```

文档元数据、版本和索引状态归 `documents`，来源内容由 `infra` 提供存储能力。
