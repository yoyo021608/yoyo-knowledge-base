import { ApiError } from "./auth";
import { buildApiUrl } from "./client";

export type SessionStatus = "active" | "deleting";
export type MessageRole = "user" | "assistant";
export type TaskResultKind = "research" | "comparison";
export type TaskStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type FeedbackTarget = "message" | "citation" | "practice";
export type FeedbackRating = -1 | 1;

/** 会话自身的状态；回答内容和运行状态分别由 history 与 agent 管理。 */
export interface ConversationSession {
  id: string;
  userId: string;
  name: string;
  status: SessionStatus;
  activeRunId: string | null;
  createdAt: string;
  updatedAt: string;
}

/** 回答生成时冻结的证据，原文后续更新也不会改变历史引用。 */
export interface Citation {
  id: string;
  messageId: string;
  documentId: string;
  documentVersionId: string;
  chunkId: string;
  titleSnapshot: string;
  quote: string;
  sourceUrl: string | null;
}

export interface ConversationMessage {
  id: string;
  sessionId: string;
  runId: string;
  role: MessageRole;
  content: string;
  citations: Citation[];
  createdAt: string;
}

/** 研究和对比模式持久化的可回放结果。 */
export interface TaskResult {
  id: string;
  sessionId: string;
  runId: string;
  kind: TaskResultKind;
  question: string;
  status: TaskStatus;
  result: unknown | null;
  failureReason: string | null;
  createdAt: string;
  updatedAt: string;
}

/** 学习模式的一次作答结果及当时的掌握度快照。 */
export interface PracticeRecord {
  id: string;
  sessionId: string;
  runId: string;
  question: string;
  answer: string;
  verdict: string;
  explanation: string;
  masterySnapshot: unknown;
  createdAt: string;
}

export interface SessionFeedback {
  id: string;
  sessionId: string;
  targetType: FeedbackTarget;
  targetId: string;
  rating: FeedbackRating;
  comment: string;
  createdAt: string;
}

interface ErrorWireResponse {
  detail?: string;
}

type JsonBody = Record<string, unknown> | unknown[];

/** sessions 的认证请求边界；页面不直接处理蛇形字段或后端错误格式。 */
async function request<T>(
  baseUrl: string,
  accessToken: string,
  path: string,
  method = "GET",
  body?: JsonBody,
): Promise<T> {
  const response = await fetch(buildApiUrl(baseUrl, path), {
    method,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await response.text();
  if (!response.ok) {
    let message = `请求失败：HTTP ${response.status}`;
    if (text) {
      try {
        const error = JSON.parse(text) as ErrorWireResponse;
        if (typeof error.detail === "string") message = error.detail;
      } catch {
        // 网关可能返回非 JSON 内容，此时保留稳定的状态码提示。
      }
    }
    throw new ApiError(message, response.status);
  }
  return (text ? JSON.parse(text) : undefined) as T;
}

function parseStoredJson(value: unknown): unknown | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    // 历史数据损坏时仍允许页面展示原值，避免整个记录列表不可用。
    return value;
  }
}

function sessionOf(raw: Record<string, unknown>): ConversationSession {
  return {
    id: String(raw.id),
    userId: String(raw.user_id),
    name: String(raw.name),
    status: raw.status as SessionStatus,
    activeRunId: (raw.active_run_id as string | null) ?? null,
    createdAt: String(raw.created_at),
    updatedAt: String(raw.updated_at),
  };
}

function citationOf(raw: Record<string, unknown>): Citation {
  return {
    id: String(raw.id),
    messageId: String(raw.message_id),
    documentId: String(raw.document_id),
    documentVersionId: String(raw.document_version_id),
    chunkId: String(raw.chunk_id),
    titleSnapshot: String(raw.title_snapshot),
    quote: String(raw.quote),
    sourceUrl: (raw.source_url as string | null) ?? null,
  };
}

function messageOf(raw: Record<string, unknown>): ConversationMessage {
  const citations = (raw.citations as Record<string, unknown>[] | undefined) ?? [];
  return {
    id: String(raw.id),
    sessionId: String(raw.session_id),
    runId: String(raw.run_id),
    role: raw.role as MessageRole,
    content: String(raw.content),
    citations: citations.map(citationOf),
    createdAt: String(raw.created_at),
  };
}

function taskResultOf(raw: Record<string, unknown>): TaskResult {
  return {
    id: String(raw.id),
    sessionId: String(raw.session_id),
    runId: String(raw.run_id),
    kind: raw.kind as TaskResultKind,
    question: String(raw.question),
    status: raw.status as TaskStatus,
    result: parseStoredJson(raw.result_json),
    failureReason: (raw.failure_reason as string | null) ?? null,
    createdAt: String(raw.created_at),
    updatedAt: String(raw.updated_at),
  };
}

function practiceOf(raw: Record<string, unknown>): PracticeRecord {
  return {
    id: String(raw.id),
    sessionId: String(raw.session_id),
    runId: String(raw.run_id),
    question: String(raw.question),
    answer: String(raw.answer),
    verdict: String(raw.verdict),
    explanation: String(raw.explanation),
    masterySnapshot: parseStoredJson(raw.mastery_snapshot_json),
    createdAt: String(raw.created_at),
  };
}

function feedbackOf(raw: Record<string, unknown>): SessionFeedback {
  return {
    id: String(raw.id),
    sessionId: String(raw.session_id),
    targetType: raw.target_type as FeedbackTarget,
    targetId: String(raw.target_id),
    rating: Number(raw.rating) as FeedbackRating,
    comment: String(raw.comment),
    createdAt: String(raw.created_at),
  };
}

export async function createSession(
  baseUrl: string,
  accessToken: string,
  name = "新会话",
): Promise<ConversationSession> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    "/api/sessions",
    "POST",
    { name },
  );
  return sessionOf(raw);
}

export async function listSessions(
  baseUrl: string,
  accessToken: string,
): Promise<ConversationSession[]> {
  const raw = await request<Record<string, unknown>[]>(baseUrl, accessToken, "/api/sessions");
  return raw.map(sessionOf);
}

export async function getSession(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<ConversationSession> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}`,
  );
  return sessionOf(raw);
}

export async function renameSession(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
  name: string,
): Promise<ConversationSession> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}`,
    "PATCH",
    { name },
  );
  return sessionOf(raw);
}

/** 按后端协议先阻止新 Run，再协调清理 Agent 数据并删除会话。 */
export async function deleteSession(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<void> {
  const path = `/api/sessions/${encodeURIComponent(sessionId)}`;
  await request<void>(baseUrl, accessToken, `${path}/delete`, "POST");
  await request<void>(baseUrl, accessToken, path, "DELETE");
}

export async function listSessionMessages(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<ConversationMessage[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}/messages`,
  );
  return raw.map(messageOf);
}

export async function listMessageCitations(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
  messageId: string,
): Promise<Citation[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/citations`,
  );
  return raw.map(citationOf);
}

export async function listTaskResults(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<TaskResult[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}/results`,
  );
  return raw.map(taskResultOf);
}

export async function listPracticeRecords(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<PracticeRecord[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}/practice`,
  );
  return raw.map(practiceOf);
}

export async function saveSessionFeedback(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
  input: {
    targetType: FeedbackTarget;
    targetId: string;
    rating: FeedbackRating;
    comment?: string;
  },
): Promise<SessionFeedback> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}/feedback`,
    "PUT",
    {
      target_type: input.targetType,
      target_id: input.targetId,
      rating: input.rating,
      comment: input.comment ?? "",
    },
  );
  return feedbackOf(raw);
}

export async function listSessionFeedback(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<SessionFeedback[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/sessions/${encodeURIComponent(sessionId)}/feedback`,
  );
  return raw.map(feedbackOf);
}
