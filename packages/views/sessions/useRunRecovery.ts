import { useCallback, useEffect, useRef, useState } from "react";

import {
  askAgentQuestion,
  cancelAgentRun,
  continueAgentRun,
  getAgentRun,
  listAgentRunEvents,
  type AgentRun,
  type AgentRunEvent,
  type QuestionInput,
  type QuestionResult,
} from "@yoyo/core";

import {
  isTerminalRun,
  latestEventSequence,
  mergeRunEvents,
} from "./runState";

export interface RunDraftStore {
  load(requestId: string): QuestionInput | null;
  save(requestId: string, input: QuestionInput): void;
  remove(requestId: string): void;
}

interface Options {
  apiBaseUrl: string;
  accessToken: string;
  sessionId: string | null;
  activeRunId: string | null;
  draftStore?: RunDraftStore;
  onTerminal: () => Promise<void>;
}

interface RunRecoveryState {
  run: AgentRun | null;
  events: AgentRunEvent[];
  /** 兼容现有结果展示；异步运行的最终回答由 sessions 历史刷新取得。 */
  result: QuestionResult | null;
  pending: boolean;
  error: string;
  ask: (input: QuestionInput) => Promise<void>;
  cancel: () => Promise<void>;
  resume: () => Promise<void>;
  refresh: () => Promise<void>;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "运行操作失败";
}

function createMemoryDraftStore(): RunDraftStore {
  const drafts = new Map<string, QuestionInput>();
  return {
    load: (requestId) => drafts.get(requestId) ?? null,
    save: (requestId, input) => drafts.set(requestId, input),
    remove: (requestId) => drafts.delete(requestId),
  };
}

/** 浏览器存储不可用时退回当前页面内存，不能让存储异常阻断 Run 主流程。 */
function saveDraft(
  primary: RunDraftStore,
  fallback: RunDraftStore,
  requestId: string,
  input: QuestionInput,
): void {
  try {
    primary.save(requestId, input);
  } catch {
    // 外部存储失败时仍保留当前页面内的恢复参数。
  }
  fallback.save(requestId, input);
}

function removeDraft(
  primary: RunDraftStore,
  fallback: RunDraftStore,
  requestId: string,
): void {
  try {
    primary.remove(requestId);
  } catch {
    // 外部存储清理失败不能阻断终态数据刷新。
  }
  fallback.remove(requestId);
}

/**
 * Agent 运行视图状态：只读取后端 Run 和持久化事件。
 * sessions 的消息刷新由 onTerminal 交回组合层处理。
 */
export function useRunRecovery({
  apiBaseUrl,
  accessToken,
  sessionId,
  activeRunId,
  draftStore,
  onTerminal,
}: Options): RunRecoveryState {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [events, setEvents] = useState<AgentRunEvent[]>([]);
  const [result, setResult] = useState<QuestionResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const eventsRef = useRef<AgentRunEvent[]>([]);
  const runRef = useRef<AgentRun | null>(null);
  const runScopeRef = useRef("");
  const memoryDraftStore = useRef<RunDraftStore>(createMemoryDraftStore()).current;
  const activeDraftStore = draftStore ?? memoryDraftStore;

  useEffect(() => {
    eventsRef.current = events;
  }, [events]);

  useEffect(() => {
    runRef.current = run;
  }, [run]);

  runScopeRef.current = `${sessionId ?? ""}:${activeRunId ?? ""}`;

  useEffect(() => {
    setRun(null);
    setEvents([]);
    setResult(null);
    setError("");
    runRef.current = null;
    eventsRef.current = [];
  }, [sessionId]);

  const refreshRun = useCallback(
    async (runId?: string): Promise<AgentRun | null> => {
      const id = runId ?? runRef.current?.id ?? activeRunId;
      if (!id) return null;
      const expectedScope = runScopeRef.current;
      // 先读 Run，再补事件；若这里已经是终态，终态事件也已经完成持久化。
      const nextRun = await getAgentRun(apiBaseUrl, accessToken, id);
      let cursor = latestEventSequence(eventsRef.current);
      const incoming: AgentRunEvent[] = [];
      // 终态 Run 也可能有多页事件，持续按游标读取直到当前页末。
      while (true) {
        const page = await listAgentRunEvents(apiBaseUrl, accessToken, id, {
          afterSeq: cursor,
          limit: 500,
        });
        incoming.push(...page);
        if (page.length < 500) break;
        const nextCursor = latestEventSequence(page);
        if (nextCursor <= cursor) break;
        cursor = nextCursor;
      }
      if (runScopeRef.current !== expectedScope) return null;
      setRun((current) => {
        if (
          current?.id === nextRun.id
          && Date.parse(current.updatedAt) > Date.parse(nextRun.updatedAt)
        ) {
          return current;
        }
        return current?.id === nextRun.id
          && isTerminalRun(current.status)
          && !isTerminalRun(nextRun.status)
          ? current
          : nextRun;
      });
      setEvents((current) => mergeRunEvents(current, incoming));
      setError("");
      return nextRun;
    },
    [accessToken, activeRunId, apiBaseUrl],
  );

  useEffect(() => {
    if (!activeRunId) return;
    let cancelled = false;
    if (runRef.current?.id !== activeRunId) {
      setRun(null);
      setResult(null);
      setError("");
      runRef.current = null;
    }
    setEvents([]);
    eventsRef.current = [];
    void refreshRun(activeRunId)
      .then((nextRun) => {
        if (!cancelled && nextRun && isTerminalRun(nextRun.status)) {
          removeDraft(activeDraftStore, memoryDraftStore, nextRun.requestId);
          return onTerminal();
        }
        return undefined;
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(errorMessage(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [activeDraftStore, activeRunId, memoryDraftStore, onTerminal, refreshRun]);

  useEffect(() => {
    if (!run || isTerminalRun(run.status)) return;
    let stopped = false;
    let timer: number | undefined;
    const poll = async (): Promise<void> => {
      let terminal = false;
      try {
        const nextRun = await refreshRun();
        terminal = Boolean(nextRun && isTerminalRun(nextRun.status));
        if (!stopped && nextRun && terminal) {
          removeDraft(activeDraftStore, memoryDraftStore, nextRun.requestId);
          await onTerminal();
        }
      } catch (reason) {
        // 临时断网只更新提示，下一轮仍继续从最后 eventSeq 补读。
        setError(errorMessage(reason));
      }
      if (!stopped && !terminal) timer = window.setTimeout(() => void poll(), 1500);
    };
    timer = window.setTimeout(() => void poll(), 1500);
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [activeDraftStore, memoryDraftStore, onTerminal, refreshRun, run?.id, run?.status]);

  const ask = useCallback(
    async (input: QuestionInput): Promise<void> => {
      setPending(true);
      setError("");
      setResult(null);
      try {
        saveDraft(activeDraftStore, memoryDraftStore, input.requestId, input);
        const acceptedRun = await askAgentQuestion(apiBaseUrl, accessToken, input);
        setRun(acceptedRun);
        const nextRun = await refreshRun(acceptedRun.id);
        if (nextRun && isTerminalRun(nextRun.status)) {
          removeDraft(activeDraftStore, memoryDraftStore, nextRun.requestId);
          await onTerminal();
        }
      } catch (reason) {
        setError(errorMessage(reason));
        throw reason;
      } finally {
        setPending(false);
      }
    },
    [accessToken, activeDraftStore, apiBaseUrl, memoryDraftStore, onTerminal, refreshRun],
  );

  const cancel = useCallback(async (): Promise<void> => {
    if (!run) return;
    setPending(true);
    setError("");
    try {
      const cancelledRun = await cancelAgentRun(apiBaseUrl, accessToken, run.id);
      setRun(cancelledRun);
      removeDraft(activeDraftStore, memoryDraftStore, cancelledRun.requestId);
      await refreshRun(cancelledRun.id);
      await onTerminal();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }, [accessToken, activeDraftStore, apiBaseUrl, memoryDraftStore, onTerminal, refreshRun, run]);

  const resume = useCallback(async (): Promise<void> => {
    if (!run) return;
    setPending(true);
    setError("");
    try {
      const continuedRun = await continueAgentRun(apiBaseUrl, accessToken, run.id);
      setRun(continuedRun);
      const nextRun = await refreshRun(run.id);
      if (nextRun && isTerminalRun(nextRun.status)) {
        removeDraft(activeDraftStore, memoryDraftStore, nextRun.requestId);
        await onTerminal();
      }
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }, [accessToken, activeDraftStore, apiBaseUrl, memoryDraftStore, onTerminal, refreshRun, run]);

  return {
    run,
    events,
    result,
    pending,
    error,
    ask,
    cancel,
    resume,
    refresh: async () => {
      await refreshRun();
    },
  };
}
