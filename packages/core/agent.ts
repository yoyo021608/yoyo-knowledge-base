import { ApiError } from "./auth";
import { buildApiUrl } from "./client";

export type AgentMode = "quick" | "research" | "comparison" | "study";
export type RunStatus =
  | "queued"
  | "running"
  | "paused"
  | "finalizing"
  | "cancelled"
  | "completed"
  | "failed";
export type RunStep = "rewrite" | "retrieve" | "generate" | "persist_answer";
export type EvidenceStatus = "sufficient" | "insufficient" | "failed";
/** 一次提问的范围参数；身份只来自 accessToken，不允许调用方传 userId。 */
export interface QuestionInput {
  sessionId: string;
  requestId: string;
  question: string;
  mode?: AgentMode;
  topicId?: string;
  tag?: string;
  documentIds?: string[];
  versionIds?: string[];
  userAnswer?: string;
}

/** 已持久化回答的引用快照类型，暂时保留供现有会话展示层使用。 */
export interface AnswerCitation {
  documentId: string;
  documentVersionId: string;
  chunkId: string;
  titleSnapshot: string;
  sourceUrl: string | null;
  quote: string;
}

export interface AgentAnswer {
  text: string;
  citations: AnswerCitation[];
  evidenceStatus: EvidenceStatus;
}

export interface RunEvaluation {
  hitCount: number;
  citationCoverage: number;
  evidenceStatus: EvidenceStatus;
  failureReason: string | null;
}

/** 兼容现有展示组件；异步提交接口不再直接返回该结构。 */
export interface QuestionResult {
  runId: string;
  status: RunStatus;
  messageId: string | null;
  answer: AgentAnswer;
  evaluation: RunEvaluation;
  modeResult: Record<string, unknown> | null;
}

/** Run 是可恢复任务的唯一状态来源，前端不能根据本地步骤推断终态。 */
export interface AgentRun {
  id: string;
  sessionId: string;
  requestId: string;
  mode: AgentMode;
  status: RunStatus;
  lastEventSeq: number;
  failureReason: string | null;
  step: RunStep;
  revision: number;
  createdAt: string;
  updatedAt: string;
}

/** 按 eventSeq 增量回放的运行事件；payload 由事件类型决定。 */
export interface AgentRunEvent {
  id: string;
  runId: string;
  eventSeq: number;
  eventType: string;
  payload: unknown;
  createdAt: string;
}

export interface RunEventQuery {
  afterSeq?: number;
  limit?: number;
}

interface ErrorWireResponse {
  detail?: string;
}

/** agent 的认证请求边界；业务状态完全采用后端 Run 与事件响应。 */
async function request<T>(
  baseUrl: string,
  accessToken: string,
  path: string,
  method = "GET",
  body?: Record<string, unknown>,
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
        // 非 JSON 错误继续使用状态码提示。
      }
    }
    throw new ApiError(message, response.status);
  }
  return (text ? JSON.parse(text) : undefined) as T;
}

function runOf(raw: Record<string, unknown>): AgentRun {
  return {
    id: String(raw.id),
    sessionId: String(raw.session_id),
    requestId: String(raw.request_id),
    mode: raw.mode as AgentMode,
    status: raw.status as RunStatus,
    lastEventSeq: Number(raw.last_event_seq),
    failureReason: (raw.failure_reason as string | null) ?? null,
    step: raw.step as RunStep,
    revision: Number(raw.revision),
    createdAt: String(raw.created_at),
    updatedAt: String(raw.updated_at),
  };
}

function eventPayloadOf(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    // 保留未知事件的原始载荷，保证新事件类型可以向前兼容。
    return value;
  }
}

export async function askAgentQuestion(
  baseUrl: string,
  accessToken: string,
  input: QuestionInput,
): Promise<AgentRun> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    "/api/agent/questions",
    "POST",
    {
      session_id: input.sessionId,
      request_id: input.requestId,
      question: input.question,
      mode: input.mode ?? "quick",
      topic_id: input.topicId ?? null,
      tag: input.tag ?? null,
      document_ids: input.documentIds ?? [],
      version_ids: input.versionIds ?? [],
      user_answer: input.userAnswer ?? null,
    },
  );
  return runOf(raw);
}

export async function getAgentRun(
  baseUrl: string,
  accessToken: string,
  runId: string,
): Promise<AgentRun> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/agent/runs/${encodeURIComponent(runId)}`,
  );
  return runOf(raw);
}

export async function listAgentRunEvents(
  baseUrl: string,
  accessToken: string,
  runId: string,
  query: RunEventQuery = {},
): Promise<AgentRunEvent[]> {
  const search = new URLSearchParams({
    after_seq: String(query.afterSeq ?? 0),
    limit: String(query.limit ?? 100),
  });
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/agent/runs/${encodeURIComponent(runId)}/events?${search.toString()}`,
  );
  return raw.map((event) => ({
    id: String(event.id),
    runId: String(event.run_id),
    eventSeq: Number(event.event_seq),
    eventType: String(event.event_type),
    payload: eventPayloadOf(event.payload),
    createdAt: String(event.created_at),
  }));
}

export async function cancelAgentRun(
  baseUrl: string,
  accessToken: string,
  runId: string,
): Promise<AgentRun> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/agent/runs/${encodeURIComponent(runId)}/cancel`,
    "POST",
  );
  return runOf(raw);
}

/** 后端使用 Run 快照中的原始范围恢复执行，浏览器不再重传业务参数。 */
export async function continueAgentRun(
  baseUrl: string,
  accessToken: string,
  runId: string,
): Promise<AgentRun> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/agent/runs/${encodeURIComponent(runId)}/continue`,
    "POST",
  );
  return runOf(raw);
}
