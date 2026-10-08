import { useEffect, useState } from "react";

import type {
  ConversationMessage,
  FeedbackRating,
  PracticeRecord,
  SessionFeedback,
  TaskResult,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface Props {
  messages: ConversationMessage[];
  taskResults: TaskResult[];
  practice: PracticeRecord[];
  feedback: SessionFeedback[];
  onFeedback: (
    targetType: "message" | "citation" | "practice",
    targetId: string,
    rating: FeedbackRating,
    comment: string,
  ) => Promise<void>;
}

const TASK_STATUS_LABELS: Record<TaskResult["status"], string> = {
  queued: "等待执行",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const VERDICT_LABELS: Record<string, string> = {
  correct: "正确",
  partial: "部分正确",
  incorrect: "需要复习",
  insufficient_evidence: "证据不足，暂不判定",
};

function storedResult(value: unknown): string {
  return typeof value === "string"
    ? value
    : JSON.stringify(value, null, 2) ?? String(value);
}

function resultRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function SavedTaskContent({ task }: { task: TaskResult }) {
  const result = resultRecord(task.result);
  if (!result) return task.result === null ? null : <pre>{storedResult(task.result)}</pre>;
  const mainKey = task.kind === "research" ? "report" : "summary";
  const main = typeof result[mainKey] === "string" ? result[mainKey] : null;
  const subquestions = stringList(result.subquestions);
  const unresolved = stringList(result.unresolved_questions);
  const comparedCount = typeof result.compared_scope_count === "number"
    ? result.compared_scope_count
    : null;
  if (!main && subquestions.length === 0 && unresolved.length === 0 && comparedCount === null) {
    return <pre>{storedResult(task.result)}</pre>;
  }
  return (
    <div>
      {main && <p>{main}</p>}
      {subquestions.length > 0 && <p>研究子问题：{subquestions.join("；")}</p>}
      {unresolved.length > 0 && <p>仍缺少证据：{unresolved.join("；")}</p>}
      {comparedCount !== null && <p>已对齐 {comparedCount} 个文档版本的依据</p>}
    </div>
  );
}

function safeSourceUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function FeedbackButtons({
  targetType,
  targetId,
  feedback,
  onFeedback,
}: {
  targetType: "message" | "citation" | "practice";
  targetId: string;
  feedback: SessionFeedback[];
  onFeedback: Props["onFeedback"];
}) {
  const current = feedback.find(
    (item) => item.targetType === targetType && item.targetId === targetId,
  );
  const [comment, setComment] = useState(current?.comment ?? "");
  useEffect(() => setComment(current?.comment ?? ""), [current?.comment]);
  return (
    <div className="feedback-box">
      <input
        value={comment}
        maxLength={500}
        placeholder="补充反馈（可选）"
        onChange={(event) => setComment(event.target.value)}
      />
      <span className="feedback-actions">
        <Button onClick={() => void onFeedback(targetType, targetId, 1, comment)}>{current?.rating === 1 ? "已赞" : "有帮助"}</Button>
        <Button onClick={() => void onFeedback(targetType, targetId, -1, comment)}>{current?.rating === -1 ? "已踩" : "需改进"}</Button>
      </span>
    </div>
  );
}

/** 历史消息和结果以 sessions 数据为准；引用展示固定版本和摘录。 */
export function ConversationHistory({
  messages,
  taskResults,
  practice,
  feedback,
  onFeedback,
}: Props) {
  return (
    <Card>
      <h2>会话历史</h2>
      {messages.length === 0 && <p className="muted">从下方写下问题，让第一次探索从这里开始</p>}
      <ol className="message-list">
        {messages.map((message) => (
          <li className={`message message-${message.role}`} key={message.id}>
            <header><strong>{message.role === "user" ? "我" : "知识助手"}</strong><time>{new Date(message.createdAt).toLocaleString()}</time></header>
            <p>{message.content}</p>
            {message.citations.length > 0 && (
              <details>
                <summary>引用（{message.citations.length}）</summary>
                <ol className="citation-list">
                  {message.citations.map((citation) => (
                    <li key={citation.id}>
                      <strong>{citation.titleSnapshot}</strong>
                      <blockquote>{citation.quote}</blockquote>
                      <small>版本 {citation.documentVersionId} · 片段 {citation.chunkId}</small>
                      {safeSourceUrl(citation.sourceUrl) && (
                        <a href={safeSourceUrl(citation.sourceUrl) ?? undefined} target="_blank" rel="noreferrer">查看来源</a>
                      )}
                      <FeedbackButtons targetType="citation" targetId={citation.id} feedback={feedback} onFeedback={onFeedback} />
                    </li>
                  ))}
                </ol>
              </details>
            )}
            {message.role === "assistant" && <FeedbackButtons targetType="message" targetId={message.id} feedback={feedback} onFeedback={onFeedback} />}
          </li>
        ))}
      </ol>

      {taskResults.length > 0 && (
        <details>
          <summary>研究与对比结果（{taskResults.length}）</summary>
          {taskResults.map((task) => (
            <article className="saved-result" key={task.id}>
              <strong>{task.kind === "research" ? "研究" : "对比"}：{task.question}</strong>
              <p>状态：{TASK_STATUS_LABELS[task.status]}</p>
              <SavedTaskContent task={task} />
              {task.failureReason && <p role="alert">{task.failureReason}</p>}
            </article>
          ))}
        </details>
      )}

      {practice.length > 0 && (
        <details>
          <summary>练习记录（{practice.length}）</summary>
          {practice.map((item) => (
            <article className="saved-result" key={item.id}>
              <strong>{item.question}</strong>
              <p>作答：{item.answer}</p>
              <p>判断：{VERDICT_LABELS[item.verdict] ?? item.verdict}；{item.explanation}</p>
              <details><summary>掌握度快照</summary><pre>{storedResult(item.masterySnapshot)}</pre></details>
              <FeedbackButtons targetType="practice" targetId={item.id} feedback={feedback} onFeedback={onFeedback} />
            </article>
          ))}
        </details>
      )}
    </Card>
  );
}
