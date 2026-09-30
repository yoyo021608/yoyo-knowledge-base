import { useCallback, useEffect, useState } from "react";

import {
  downloadDocuments,
  getDocument,
  listDocuments,
  listDocumentVersions,
  listTags,
  listTopics,
  type DocumentDetail,
  type DocumentSummary,
  type DocumentVersion,
  type SourceType,
  type Tag,
  type Topic,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

import { DocumentDetailPanel } from "./documents/DocumentDetailPanel";
import { DocumentImportPanel } from "./documents/DocumentImportPanel";
import { DocumentSearchPanel } from "./documents/DocumentSearchPanel";
import { OrganizationPanel } from "./documents/OrganizationPanel";

interface Props {
  apiBaseUrl: string;
  accessToken: string | null;
}

/** 组合 documents 的各业务视图，数据读取与状态刷新集中在这一层。 */
export function DocumentsView({ apiBaseUrl, accessToken }: Props) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [archived, setArchived] = useState<DocumentSummary[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [message, setMessage] = useState("");
  const [keyword, setKeyword] = useState("");
  const [topicFilter, setTopicFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceType | "">("");
  const [indexFilter, setIndexFilter] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);

  const showMessage = useCallback((value: string) => setMessage(value), []);

  const load = useCallback(
    async (documentId?: string): Promise<void> => {
      if (!accessToken) return;
      const [activeDocuments, archivedDocuments, topicValues, tagValues] =
        await Promise.all([
          listDocuments(apiBaseUrl, accessToken, {
            status: "active",
            keyword: keyword || undefined,
            topicId: topicFilter || undefined,
            tag: tagFilter || undefined,
            sourceType: sourceFilter || undefined,
            indexStatus: indexFilter || undefined,
            isFavorite: favoriteOnly || undefined,
          }),
          listDocuments(apiBaseUrl, accessToken, { status: "archived" }),
          listTopics(apiBaseUrl, accessToken),
          listTags(apiBaseUrl, accessToken),
        ]);
      setDocuments(activeDocuments);
      setArchived(archivedDocuments);
      setTopics(topicValues);
      setTags(tagValues);
      if (documentId) {
        const [nextDetail, nextVersions] = await Promise.all([
          getDocument(apiBaseUrl, accessToken, documentId),
          listDocumentVersions(apiBaseUrl, accessToken, documentId),
        ]);
        setDetail(nextDetail);
        setVersions(nextVersions);
      } else {
        setDetail(null);
        setVersions([]);
      }
    },
    [accessToken, apiBaseUrl, favoriteOnly, indexFilter, keyword, sourceFilter, tagFilter, topicFilter],
  );

  useEffect(() => {
    void load().catch((error: unknown) =>
      setMessage(error instanceof Error ? error.message : "读取知识库失败"),
    );
  }, [load]);

  async function download(format: "markdown" | "json", documentId?: string): Promise<void> {
    if (!accessToken) return;
    try {
      const download = await downloadDocuments(apiBaseUrl, accessToken, format, {
        documentIds: documentId ? [documentId] : undefined,
      });
      const blob = new Blob([download.content], { type: download.mediaType });
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = `knowledge-base.${format === "markdown" ? "md" : "json"}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出失败");
    }
  }

  if (!accessToken) {
    return (
      <main className="page-shell">
        <Card>
          <h1>个人知识库</h1>
          <p>请先到账户页面登录，再录入和管理自己的资料。</p>
        </Card>
      </main>
    );
  }

  return (
    <main className="knowledge-shell">
      <header className="knowledge-header">
        <div>
          <h1>个人知识库</h1>
          <p className="muted">版本可追溯、来源可复核、候选片段可检索。</p>
        </div>
        <div className="account-actions">
          <Button onClick={() => void download("markdown")}>导出 Markdown</Button>
          <Button onClick={() => void download("json")}>导出 JSON</Button>
          {detail && <Button onClick={() => void download("markdown", detail.document.id)}>导出当前文档</Button>}
        </div>
      </header>
      {message && <p className="notice" role="status">{message}</p>}

      <div className="knowledge-grid">
        <aside className="knowledge-sidebar">
          <Card>
            <h2>文档</h2>
            <div className="document-filters">
              <input placeholder="搜索标题" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
              <select value={topicFilter} onChange={(event) => setTopicFilter(event.target.value)}><option value="">全部专题</option>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</select>
              <select value={tagFilter} onChange={(event) => setTagFilter(event.target.value)}><option value="">全部标签</option>{tags.map((tag) => <option key={tag.id} value={tag.name}>{tag.name}</option>)}</select>
              <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as SourceType | "")}><option value="">全部来源</option><option value="note">笔记</option><option value="markdown">Markdown</option><option value="web">网页</option><option value="file">文件</option></select>
              <select value={indexFilter} onChange={(event) => setIndexFilter(event.target.value)}><option value="">全部索引状态</option><option value="queued">排队中</option><option value="processing">处理中</option><option value="ready">可检索</option><option value="failed">失败</option></select>
              <label><input type="checkbox" checked={favoriteOnly} onChange={(event) => setFavoriteOnly(event.target.checked)} />只看收藏</label>
              <Button onClick={() => void load()}>应用筛选</Button>
            </div>
            <ul className="document-list">
              {documents.map((document) => (
                <li key={document.id}>
                  <button className={detail?.document.id === document.id ? "selected" : ""} onClick={() => void load(document.id)}>
                    <strong>{document.isFavorite ? "★ " : ""}{document.title}</strong>
                    <small>v{document.currentVersion} · {document.indexStatus}</small>
                  </button>
                </li>
              ))}
            </ul>
            <details>
              <summary>已归档（{archived.length}）</summary>
              <ul className="document-list">{archived.map((document) => <li key={document.id}><button onClick={() => void load(document.id)}>{document.title}</button></li>)}</ul>
            </details>
          </Card>
          <OrganizationPanel
            apiBaseUrl={apiBaseUrl}
            accessToken={accessToken}
            topics={topics}
            tags={tags}
            onChanged={() => load(detail?.document.id)}
            onMessage={showMessage}
          />
        </aside>

        <section className="knowledge-content">
          <DocumentSearchPanel apiBaseUrl={apiBaseUrl} accessToken={accessToken} onSelect={(id) => void load(id)} onMessage={showMessage} />
          <DocumentImportPanel apiBaseUrl={apiBaseUrl} accessToken={accessToken} topics={topics} onChanged={load} onMessage={showMessage} />
          {detail && (
            <DocumentDetailPanel
              apiBaseUrl={apiBaseUrl}
              accessToken={accessToken}
              detail={detail}
              versions={versions}
              documents={[...documents, ...archived]}
              topics={topics}
              onChanged={load}
              onMessage={showMessage}
            />
          )}
        </section>
      </div>
    </main>
  );
}
