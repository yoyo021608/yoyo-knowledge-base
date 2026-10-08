import { type FormEvent, useState } from "react";

import {
  listDocumentVersions,
  type AgentMode,
  type DocumentSummary,
  type DocumentVersion,
  type QuestionInput,
  type Tag,
  type Topic,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface Props {
  apiBaseUrl: string;
  accessToken: string;
  sessionId: string;
  documents: DocumentSummary[];
  topics: Topic[];
  tags: Tag[];
  disabled: boolean;
  initialQuestion?: { mode: AgentMode; question: string } | null;
  onAsk: (input: QuestionInput) => Promise<void>;
}

function requestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** 四种 Agent 模式共用的提问入口，范围参数保持显式，不替后端决定检索策略。 */
export function QuestionComposer({
  apiBaseUrl,
  accessToken,
  sessionId,
  documents,
  topics,
  tags,
  disabled,
  initialQuestion,
  onAsk,
}: Props) {
  const [question, setQuestion] = useState(initialQuestion?.question ?? "");
  const [mode, setMode] = useState<AgentMode>(initialQuestion?.mode ?? "quick");
  const [topicId, setTopicId] = useState("");
  const [tag, setTag] = useState("");
  const [documentIds, setDocumentIds] = useState<string[]>([]);
  const [versionIds, setVersionIds] = useState<string[]>([]);
  const [versionsByDocument, setVersionsByDocument] = useState<Record<string, DocumentVersion[]>>({});
  const [userAnswer, setUserAnswer] = useState("");
  const [validation, setValidation] = useState("");

  async function toggleDocument(documentId: string): Promise<void> {
    const selecting = !documentIds.includes(documentId);
    setDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((value) => value !== documentId)
        : [...current, documentId],
    );
    if (!selecting) {
      const removedVersionIds = new Set(
        (versionsByDocument[documentId] ?? []).map((version) => version.id),
      );
      setVersionIds((current) => current.filter((value) => !removedVersionIds.has(value)));
    }
    if (selecting && versionsByDocument[documentId] === undefined) {
      try {
        const versions = await listDocumentVersions(apiBaseUrl, accessToken, documentId);
        setVersionsByDocument((current) => ({ ...current, [documentId]: versions }));
      } catch (error) {
        setValidation(error instanceof Error ? error.message : "读取文档版本失败");
      }
    }
  }

  function toggleVersion(versionId: string): void {
    setVersionIds((current) =>
      current.includes(versionId)
        ? current.filter((value) => value !== versionId)
        : [...current, versionId],
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const currentVersionIds = documents
      .filter((document) => documentIds.includes(document.id))
      .map((document) => document.currentVersionId);
    const comparedVersionIds = new Set([...currentVersionIds, ...versionIds]);
    if (mode === "comparison" && comparedVersionIds.size < 2) {
      setValidation("文档对比至少选择两个文档或版本");
      return;
    }
    setValidation("");
    try {
      await onAsk({
        sessionId,
        requestId: requestId(),
        question,
        mode,
        topicId: topicId || undefined,
        tag: tag || undefined,
        documentIds: mode === "comparison" ? documentIds : [],
        // 一旦显式选择历史版本，后端会按 versionIds 查询；同时补入已选文档的
        // 当前版本，避免“当前版本 + 历史版本”对比时只检索到历史版本。
        versionIds: mode === "comparison" && versionIds.length > 0
          ? [...comparedVersionIds]
          : [],
        userAnswer: mode === "study" && userAnswer ? userAnswer : undefined,
      });
      if (mode === "study" && !userAnswer) {
        setValidation("练习已生成，请保留当前问题，填写答案后再次提交");
      } else {
        setQuestion("");
        setUserAnswer("");
      }
    } catch {
      // 运行错误已由 useRunRecovery 记录，保留问题文本方便用户修正或重试。
    }
  }

  return (
    <Card>
      <h2>使用知识</h2>
      <form className="question-form" onSubmit={(event) => void submit(event)}>
        <label>
          任务模式
          <select value={mode} onChange={(event) => setMode(event.target.value as AgentMode)}>
            <option value="quick">快速问答</option>
            <option value="research">深度研究</option>
            <option value="comparison">文档对比</option>
            <option value="study">学习模式</option>
          </select>
        </label>
        <label>
          问题
          <textarea
            required
            maxLength={20_000}
            rows={4}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </label>
        <details>
          <summary>限定知识范围</summary>
          <div className="question-scope">
            <label>专题<select value={topicId} onChange={(event) => setTopicId(event.target.value)}><option value="">全部专题</option>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</select></label>
            <label>标签<select value={tag} onChange={(event) => setTag(event.target.value)}><option value="">全部标签</option>{tags.map((value) => <option key={value.id} value={value.name}>{value.name}</option>)}</select></label>
            {mode === "comparison" && (
              <>
                <fieldset>
                  <legend>参与对比的文档</legend>
                  {documents.map((document) => (
                    <label key={document.id}>
                      <input
                        type="checkbox"
                        checked={documentIds.includes(document.id)}
                        onChange={() => void toggleDocument(document.id)}
                      />
                      {document.title}（v{document.currentVersion}）
                    </label>
                  ))}
                </fieldset>
                {Object.entries(versionsByDocument)
                  .filter(([documentId]) => documentIds.includes(documentId))
                  .map(([documentId, versions]) => {
                    const document = documents.find((item) => item.id === documentId);
                    return (
                      <fieldset key={documentId}>
                        <legend>{document?.title ?? "文档"}的历史版本</legend>
                        {versions.map((version) => (
                          <label key={version.id}>
                            <input
                              type="checkbox"
                              checked={versionIds.includes(version.id)}
                              onChange={() => toggleVersion(version.id)}
                            />
                            v{version.version} · {version.titleSnapshot}
                            {version.id === document?.currentVersionId ? "（当前版本）" : ""}
                          </label>
                        ))}
                      </fieldset>
                    );
                  })}
              </>
            )}
          </div>
        </details>
        {mode === "study" && (
          <label>
            我的答案（留空时生成练习）
            <textarea rows={3} value={userAnswer} onChange={(event) => setUserAnswer(event.target.value)} />
          </label>
        )}
        {validation && <p className="notice" role="alert">{validation}</p>}
        <Button type="submit" disabled={disabled}>{disabled ? "任务处理中…" : "开始"}</Button>
      </form>
    </Card>
  );
}
