import { type FormEvent, useState } from "react";

import {
  createBatchImport,
  importDocument,
  importDocumentFile,
  retryBatchImport,
  type BatchJobResult,
  type SourceType,
  type Topic,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface Props {
  apiBaseUrl: string;
  accessToken: string;
  topics: Topic[];
  onChanged: (documentId?: string) => Promise<void>;
  onMessage: (message: string) => void;
}

function tagsOf(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

/** 单条、文件和批量录入入口；三种入口最终都调用 documents 公开接口。 */
export function DocumentImportPanel({
  apiBaseUrl,
  accessToken,
  topics,
  onChanged,
  onMessage,
}: Props) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [sourceType, setSourceType] = useState<Exclude<SourceType, "file">>("note");
  const [sourceUrl, setSourceUrl] = useState("");
  const [topicId, setTopicId] = useState("");
  const [tags, setTags] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [batchText, setBatchText] = useState("");
  const [batch, setBatch] = useState<BatchJobResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function submitSingle(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await importDocument(apiBaseUrl, accessToken, {
        title,
        content,
        sourceType,
        sourceUrl: sourceUrl || undefined,
        topicId: topicId || undefined,
        tags: tagsOf(tags),
      });
      setTitle("");
      setContent("");
      onMessage(`录入成功，索引状态：${result.indexStatus}`);
      await onChanged(result.documentId);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "录入失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitFile(): Promise<void> {
    if (!file) return;
    setBusy(true);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (const byte of bytes) binary += String.fromCharCode(byte);
      const result = await importDocumentFile(apiBaseUrl, accessToken, {
        name: file.name,
        contentBase64: btoa(binary),
        contentType: file.type || "text/plain",
      }, {
        title: title || undefined,
        topicId: topicId || undefined,
        tags: tagsOf(tags),
      });
      setFile(null);
      onMessage(`文件录入成功，索引状态：${result.indexStatus}`);
      await onChanged(result.documentId);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "文件录入失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitBatch(): Promise<void> {
    const blocks = batchText
      .split(/\n---\n/)
      .map((value) => value.trim())
      .filter(Boolean);
    if (blocks.length === 0) {
      onMessage("批量内容不能为空");
      return;
    }
    setBusy(true);
    try {
      const result = await createBatchImport(
        apiBaseUrl,
        accessToken,
        blocks.map((block, index) => {
          const [firstLine, ...rest] = block.split("\n");
          return {
            title: firstLine.replace(/^#+\s*/, "").trim() || `批量资料 ${index + 1}`,
            content: rest.length ? rest.join("\n") : block,
            sourceType: "markdown" as const,
            topicId: topicId || undefined,
            tags: tagsOf(tags),
          };
        }),
      );
      setBatch(result);
      onMessage(`批量录入完成：成功 ${result.job.successCount}，失败 ${result.job.failureCount}`);
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "批量录入失败");
    } finally {
      setBusy(false);
    }
  }

  async function retryFailed(): Promise<void> {
    if (!batch) return;
    setBusy(true);
    try {
      const result = await retryBatchImport(apiBaseUrl, accessToken, batch.job.id);
      setBatch(result);
      onMessage(`重试完成：成功 ${result.job.successCount}，失败 ${result.job.failureCount}`);
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "重试失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2>录入资料</h2>
      <form className="document-form" onSubmit={(event) => void submitSingle(event)}>
        <label>
          标题{sourceType === "web" ? "（可由网页自动识别）" : ""}
          <input required={sourceType !== "web"} maxLength={300} value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label>
          来源类型
          <select value={sourceType} onChange={(event) => setSourceType(event.target.value as Exclude<SourceType, "file">)}>
            <option value="note">普通笔记</option>
            <option value="markdown">Markdown</option>
            <option value="web">网页内容</option>
          </select>
        </label>
        {sourceType === "web" && (
          <label>
            来源地址
            <input type="url" required value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
          </label>
        )}
        <label>
          专题
          <select value={topicId} onChange={(event) => setTopicId(event.target.value)}>
            <option value="">未归类</option>
            {topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
          </select>
        </label>
        <label>
          标签（逗号分隔）
          <input value={tags} onChange={(event) => setTags(event.target.value)} />
        </label>
        <label>
          正文{sourceType === "web" ? "（留空时自动抓取）" : ""}
          <textarea required={sourceType !== "web"} rows={8} value={content} onChange={(event) => setContent(event.target.value)} />
        </label>
        <Button type="submit" disabled={busy}>录入并建立索引</Button>
      </form>

      <details>
        <summary>上传文本、PDF、Word、CSV 或 Excel 文件</summary>
        <input type="file" accept=".txt,.md,.pdf,.docx,.csv,.xlsx,.xlsm" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <Button disabled={busy || !file} onClick={() => void submitFile()}>上传文件</Button>
      </details>

      <details>
        <summary>批量录入</summary>
        <p className="muted">每段第一行作为标题，段与段之间单独一行填写 ---。</p>
        <textarea rows={8} value={batchText} onChange={(event) => setBatchText(event.target.value)} />
        <div className="account-actions">
          <Button disabled={busy} onClick={() => void submitBatch()}>开始批量录入</Button>
          {batch?.job.failureCount ? <Button disabled={busy} onClick={() => void retryFailed()}>只重试失败条目</Button> : null}
        </div>
        {batch && <p>任务 {batch.job.status}：{batch.job.successCount}/{batch.job.totalCount} 成功</p>}
      </details>
    </Card>
  );
}
