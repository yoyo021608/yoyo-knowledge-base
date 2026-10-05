import { useCallback, useEffect, useRef, useState } from "react";

import {
  createSession,
  deleteSession,
  listDocuments,
  listPracticeRecords,
  listSessionFeedback,
  listSessionMessages,
  listSessions,
  listTags,
  listTaskResults,
  listTopics,
  renameSession,
  saveSessionFeedback,
  type ConversationMessage,
  type ConversationSession,
  type DocumentSummary,
  type FeedbackRating,
  type PracticeRecord,
  type QuestionInput,
  type SessionFeedback,
  type Tag,
  type TaskResult,
  type Topic,
} from "@yoyo/core";
import { Card } from "@yoyo/ui";

import { ConversationHistory } from "./sessions/ConversationHistory";
import { QuestionComposer } from "./sessions/QuestionComposer";
import { RunActivity } from "./sessions/RunActivity";
import { SessionSidebar } from "./sessions/SessionSidebar";
import { type RunDraftStore, useRunRecovery } from "./sessions/useRunRecovery";
import "./sessions.css";

interface Props {
  apiBaseUrl: string;
  accessToken: string | null;
  runDraftStore?: RunDraftStore;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "会话操作失败";
}

/** 组合 sessions 持久化结果和 agent 运行控制，不在视图中复制后端业务规则。 */
export function SessionsView({ apiBaseUrl, accessToken, runDraftStore }: Props) {
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [taskResults, setTaskResults] = useState<TaskResult[]>([]);
  const [practice, setPractice] = useState<PracticeRecord[]>([]);
  const [feedback, setFeedback] = useState<SessionFeedback[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const historyRequest = useRef(0);

  const selected = sessions.find((session) => session.id === selectedId) ?? null;

  const loadHistory = useCallback(async (): Promise<void> => {
    if (!accessToken || !selectedId) return;
    const request = ++historyRequest.current;
    const [nextMessages, nextTasks, nextPractice, nextFeedback] = await Promise.all([
      listSessionMessages(apiBaseUrl, accessToken, selectedId),
      listTaskResults(apiBaseUrl, accessToken, selectedId),
      listPracticeRecords(apiBaseUrl, accessToken, selectedId),
      listSessionFeedback(apiBaseUrl, accessToken, selectedId),
    ]);
    if (request !== historyRequest.current) return;
    setMessages(nextMessages);
    setTaskResults(nextTasks);
    setPractice(nextPractice);
    setFeedback(nextFeedback);
  }, [accessToken, apiBaseUrl, selectedId]);

  const loadSessions = useCallback(
    async (preferredId?: string): Promise<void> => {
      if (!accessToken) return;
      const values = await listSessions(apiBaseUrl, accessToken);
      setSessions(values);
      const candidate = preferredId ?? selectedId;
      const nextSelected = candidate && values.some((item) => item.id === candidate)
        ? candidate
        : values[0]?.id ?? null;
      if (nextSelected !== selectedId) historyRequest.current += 1;
      setSelectedId(nextSelected);
    },
    [accessToken, apiBaseUrl, selectedId],
  );

  const refreshAfterRun = useCallback(async (): Promise<void> => {
    await Promise.all([loadSessions(selectedId ?? undefined), loadHistory()]);
  }, [loadHistory, loadSessions, selectedId]);

  const runState = useRunRecovery({
    apiBaseUrl,
    accessToken: accessToken ?? "",
    sessionId: selectedId,
    activeRunId: selected?.activeRunId ?? null,
    draftStore: runDraftStore,
    onTerminal: refreshAfterRun,
  });

  useEffect(() => {
    if (!accessToken) {
      historyRequest.current += 1;
      setSessions([]);
      setSelectedId(null);
      setMessages([]);
      setTaskResults([]);
      setPractice([]);
      setFeedback([]);
      setDocuments([]);
      setTopics([]);
      setTags([]);
      return;
    }
    let active = true;
    void listSessions(apiBaseUrl, accessToken)
      .then((sessionValues) => {
        if (!active) return;
        setSessions(sessionValues);
        setSelectedId((current) => {
          const nextSelected = current && sessionValues.some((session) => session.id === current)
            ? current
            : sessionValues[0]?.id ?? null;
          if (nextSelected !== current) historyRequest.current += 1;
          return nextSelected;
        });
      })
      .catch((error: unknown) => active && setNotice(messageOf(error)));
    void Promise.all([
      listDocuments(apiBaseUrl, accessToken, { status: "active", indexStatus: "ready" }),
      listTopics(apiBaseUrl, accessToken),
      listTags(apiBaseUrl, accessToken),
    ])
      .then(([documentValues, topicValues, tagValues]) => {
        if (!active) return;
        setDocuments(documentValues);
        setTopics(topicValues);
        setTags(tagValues);
      })
      .catch((error: unknown) => active && setNotice(messageOf(error)));
    return () => {
      active = false;
      historyRequest.current += 1;
    };
  }, [accessToken, apiBaseUrl]);

  useEffect(() => {
    if (!selectedId || !accessToken) {
      setMessages([]);
      setTaskResults([]);
      setPractice([]);
      setFeedback([]);
      return;
    }
    let active = true;
    void loadHistory().catch((error: unknown) => active && setNotice(messageOf(error)));
    return () => {
      active = false;
      historyRequest.current += 1;
    };
  }, [accessToken, loadHistory, selectedId]);

  async function withPending(action: () => Promise<void>): Promise<void> {
    setPending(true);
    setNotice("");
    try {
      await action();
    } catch (error) {
      setNotice(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  async function create(name: string): Promise<void> {
    await withPending(async () => {
      if (!accessToken) return;
      const created = await createSession(apiBaseUrl, accessToken, name);
      await loadSessions(created.id);
    });
  }

  async function rename(name: string): Promise<void> {
    await withPending(async () => {
      if (!accessToken || !selectedId) return;
      await renameSession(apiBaseUrl, accessToken, selectedId, name);
      await loadSessions(selectedId);
    });
  }

  async function remove(): Promise<void> {
    await withPending(async () => {
      if (!accessToken || !selectedId) return;
      await deleteSession(apiBaseUrl, accessToken, selectedId);
      await loadSessions();
    });
  }

  async function saveFeedback(
    targetType: "message" | "citation" | "practice",
    targetId: string,
    rating: FeedbackRating,
    comment: string,
  ): Promise<void> {
    if (!accessToken || !selectedId) return;
    try {
      await saveSessionFeedback(apiBaseUrl, accessToken, selectedId, {
        targetType,
        targetId,
        rating,
        comment,
      });
      setFeedback(await listSessionFeedback(apiBaseUrl, accessToken, selectedId));
    } catch (error) {
      setNotice(messageOf(error));
    }
  }

  async function submitQuestion(input: QuestionInput): Promise<void> {
    try {
      await runState.ask(input);
    } finally {
      // 请求中断时后端可能已经创建或完成 Run，同时补读关联与最终消息。
      await Promise.allSettled([
        loadSessions(selectedId ?? undefined),
        loadHistory(),
      ]);
    }
  }

  function selectSession(sessionId: string): void {
    historyRequest.current += 1;
    setSelectedId(sessionId);
  }

  if (!accessToken) {
    return (
      <main className="page-shell">
        <Card><h1>知识问答</h1><p>请先到账户页面登录，再创建会话并使用知识库。</p></Card>
      </main>
    );
  }

  return (
    <main className="sessions-shell">
      <header className="sessions-header">
        <div><h1>知识问答</h1><p className="muted">回答绑定证据版本，运行过程可取消、继续和断线回放。</p></div>
      </header>
      {notice && <p className="notice" role="status">{notice}</p>}
      <div className="sessions-grid">
        <SessionSidebar
          sessions={sessions}
          selectedId={selectedId}
          pending={pending}
          onSelect={selectSession}
          onCreate={create}
          onRename={rename}
          onDelete={remove}
        />
        <section className="session-content">
          {selected ? (
            <>
              <ConversationHistory
                messages={messages}
                taskResults={taskResults}
                practice={practice}
                feedback={feedback}
                onFeedback={saveFeedback}
              />
              <RunActivity
                run={runState.run}
                events={runState.events}
                result={runState.result}
                pending={runState.pending}
                error={runState.error}
                onCancel={runState.cancel}
                onResume={runState.resume}
                onRefresh={runState.refresh}
              />
              <QuestionComposer
                apiBaseUrl={apiBaseUrl}
                accessToken={accessToken}
                sessionId={selected.id}
                documents={documents}
                topics={topics}
                tags={tags}
                disabled={pending || runState.pending || selected.status === "deleting" || Boolean(selected.activeRunId)}
                onAsk={submitQuestion}
              />
            </>
          ) : (
            <Card><h2>还没有会话</h2><p>先在左侧创建一个会话。</p></Card>
          )}
        </section>
      </div>
    </main>
  );
}
