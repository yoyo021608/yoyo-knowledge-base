import { type FormEvent, useEffect, useState } from "react";

import {
  archiveDocument,
  createDocumentRelation,
  deleteDocument,
  deleteDocumentRelation,
  getDocumentKnowledge,
  getDocumentVersion,
  listDocumentRelations,
  restoreDocument,
  retryDocumentIndex,
  setDocumentFavorite,
  updateDocument,
  type DocumentDetail,
  type DocumentKnowledge,
  type DocumentRelation,
  type DocumentSummary,
  type DocumentVersion,
  type Topic,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface Props {
  apiBaseUrl: string;
  accessToken: string;
  detail: DocumentDetail;
  versions: DocumentVersion[];
  documents: DocumentSummary[];
  topics: Topic[];
  onChanged: (documentId?: string) => Promise<void>;
  onMessage: (message: string) => void;
}

function tagsOf(value: string): string[] {
  return value.split(",").map((tag) => tag.trim()).filter(Boolean);
}

/** 当前文档的编辑、版本、来源、收藏、归档、删除和关联操作。 */
export function DocumentDetailPanel({
  apiBaseUrl,
  accessToken,
  detail,
  versions,
  documents,
  topics,
  onChanged,
  onMessage,
}: Props) {
  const [title, setTitle] = useState(detail.document.title);
  const [content, setContent] = useState(detail.version.contentSnapshot);
  const [topicId, setTopicId] = useState(detail.document.topicId ?? "");
  const [tags, setTags] = useState(detail.document.tags.join(", "));
  const [sourceUrl, setSourceUrl] = useState(detail.version.source.sourceUrl ?? "");
  const [relations, setRelations] = useState<DocumentRelation[]>([]);
  const [targetId, setTargetId] = useState("");
  const [relationType, setRelationType] = useState("相关资料");
  const [knowledge, setKnowledge] = useState<DocumentKnowledge | null>(null);
  const [viewedVersion, setViewedVersion] = useState<DocumentVersion | null>(null);

  useEffect(() => {
    setTitle(detail.document.title);
    setContent(detail.version.contentSnapshot);
    setTopicId(detail.document.topicId ?? "");
    setTags(detail.document.tags.join(", "));
    setSourceUrl(detail.version.source.sourceUrl ?? "");
    void listDocumentRelations(apiBaseUrl, accessToken, detail.document.id)
      .then(setRelations)
      .catch((error: unknown) => onMessage(error instanceof Error ? error.message : "读取关联失败"));
    void getDocumentKnowledge(apiBaseUrl, accessToken, detail.document.id)
      .then(setKnowledge)
      .catch((error: unknown) => onMessage(error instanceof Error ? error.message : "读取知识结构失败"));
    setViewedVersion(null);
  }, [accessToken, apiBaseUrl, detail, onMessage]);

  async function edit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      await updateDocument(apiBaseUrl, accessToken, detail.document.id, {
        title,
        content,
        topicId: topicId || undefined,
        tags: tagsOf(tags),
        sourceUrl: sourceUrl || undefined,
      });
      onMessage("已创建新版本并刷新索引");
      await onChanged(detail.document.id);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "更新失败");
    }
  }

  async function toggleFavorite(): Promise<void> {
    try {
      await setDocumentFavorite(apiBaseUrl, accessToken, detail.document.id, !detail.document.isFavorite);
      await onChanged(detail.document.id);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "收藏操作失败");
    }
  }

  async function toggleArchive(): Promise<void> {
    try {
      if (detail.document.status === "active") {
        await archiveDocument(apiBaseUrl, accessToken, detail.document.id);
        onMessage("文档已归档，默认列表和检索将立即排除它");
      } else {
        await restoreDocument(apiBaseUrl, accessToken, detail.document.id);
        onMessage("文档已恢复");
      }
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "归档操作失败");
    }
  }

  async function retryIndex(): Promise<void> {
    try {
      const nextStatus = await retryDocumentIndex(
        apiBaseUrl,
        accessToken,
        detail.document.id,
      );
      onMessage(`索引重试完成：${nextStatus}`);
      await onChanged(detail.document.id);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "索引重试失败");
    }
  }

  async function remove(): Promise<void> {
    if (!window.confirm("删除会清除正文、历史版本和索引，确定继续吗？")) return;
    try {
      await deleteDocument(apiBaseUrl, accessToken, detail.document.id);
      onMessage("文档已删除");
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  async function addRelation(): Promise<void> {
    if (!targetId) return;
    try {
      await createDocumentRelation(
        apiBaseUrl,
        accessToken,
        detail.document.id,
        targetId,
        relationType,
      );
      setRelations(await listDocumentRelations(apiBaseUrl, accessToken, detail.document.id));
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "建立关联失败");
    }
  }

  async function removeRelation(relationId: string): Promise<void> {
    try {
      await deleteDocumentRelation(apiBaseUrl, accessToken, relationId);
      setRelations(relations.filter((relation) => relation.id !== relationId));
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "解除关联失败");
    }
  }

  async function openVersion(versionId: string): Promise<void> {
    try {
      setViewedVersion(
        await getDocumentVersion(apiBaseUrl, accessToken, detail.document.id, versionId),
      );
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "读取历史版本失败");
    }
  }

  return (
    <Card>
      <div className="document-heading">
        <div>
          <h2>{detail.document.title}</h2>
          <p className="muted">版本 {detail.document.currentVersion} · 索引 {detail.document.indexStatus}</p>
        </div>
        <div className="account-actions">
          <Button onClick={() => void toggleFavorite()}>{detail.document.isFavorite ? "取消收藏" : "收藏"}</Button>
          <Button onClick={() => void toggleArchive()}>{detail.document.status === "active" ? "归档" : "恢复"}</Button>
          {detail.document.indexStatus === "failed" && <Button onClick={() => void retryIndex()}>重试索引</Button>}
          <Button onClick={() => void remove()}>删除</Button>
        </div>
      </div>

      <form className="document-form" onSubmit={(event) => void edit(event)}>
        <label>标题<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>专题<select value={topicId} onChange={(event) => setTopicId(event.target.value)}><option value="">未归类</option>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</select></label>
        <label>标签<input value={tags} onChange={(event) => setTags(event.target.value)} /></label>
        <label>来源地址<input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></label>
        <label>正文<textarea rows={12} required value={content} onChange={(event) => setContent(event.target.value)} /></label>
        <Button type="submit">保存为新版本</Button>
      </form>

      <details>
        <summary>来源快照</summary>
        <p>{detail.version.source.title}（{detail.version.source.sourceType}）</p>
        {detail.version.source.sourceUrl && <a href={detail.version.source.sourceUrl} target="_blank" rel="noreferrer">打开原网址</a>}
      </details>
      <details>
        <summary>历史版本（{versions.length}）</summary>
        <ol>{versions.map((version) => <li key={version.id}><button onClick={() => void openVersion(version.id)}>v{version.version} · {version.indexStatus} · {version.titleSnapshot}</button></li>)}</ol>
        {viewedVersion && <article className="version-preview"><h3>{viewedVersion.titleSnapshot}</h3><pre>{viewedVersion.contentSnapshot}</pre><small>来源：{viewedVersion.source.sourceUrl ?? viewedVersion.source.title}</small></article>}
      </details>
      <details>
        <summary>知识结构（{knowledge?.points.length ?? 0} 个知识点）</summary>
        {knowledge && (
          <div className="knowledge-structure">
            <div className="tag-list">{knowledge.entities.map((entity) => <span key={entity.id}>{entity.name} · {entity.entityType}</span>)}</div>
            <ol>{knowledge.points.map((point) => <li key={point.id}>{point.content}</li>)}</ol>
            <ul>{knowledge.relations.map((relation) => {
              const source = knowledge.entities.find((entity) => entity.id === relation.sourceEntityId)?.name ?? relation.sourceEntityId;
              const target = knowledge.entities.find((entity) => entity.id === relation.targetEntityId)?.name ?? relation.targetEntityId;
              return <li key={relation.id}>{source} → {relation.relationType} → {target}</li>;
            })}</ul>
          </div>
        )}
      </details>
      <details>
        <summary>文档关联（{relations.length}）</summary>
        <div className="search-row">
          <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
            <option value="">选择目标文档</option>
            {documents.filter((document) => document.id !== detail.document.id).map((document) => <option key={document.id} value={document.id}>{document.title}</option>)}
          </select>
          <input value={relationType} onChange={(event) => setRelationType(event.target.value)} />
          <Button onClick={() => void addRelation()}>建立关联</Button>
        </div>
        <ul>{relations.map((relation) => <li key={relation.id}>{relation.relationType}：{relation.sourceDocumentId === detail.document.id ? relation.targetDocumentId : relation.sourceDocumentId} <button onClick={() => void removeRelation(relation.id)}>解除</button></li>)}</ul>
      </details>
    </Card>
  );
}
