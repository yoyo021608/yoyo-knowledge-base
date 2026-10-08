import { afterEach, describe, expect, it, vi } from "vitest";

import {
  askAgentQuestion,
  deleteSession,
  listAgentRunEvents,
  listSessionMessages,
} from "@yoyo/core";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sessions core 接口", () => {
  it("转换消息和冻结引用的字段", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: "message-1",
              session_id: "session-1",
              run_id: "run-1",
              role: "assistant",
              content: "回答",
              citations: [
                {
                  id: "citation-1",
                  message_id: "message-1",
                  document_id: "document-1",
                  document_version_id: "version-1",
                  chunk_id: "chunk-1",
                  title_snapshot: "模块边界",
                  quote: "documents 负责知识本身。",
                  source_url: null,
                },
              ],
              created_at: "2026-10-04T10:00:00Z",
            },
          ]),
          { status: 200 },
        ),
      ),
    );

    const messages = await listSessionMessages(
      "http://localhost:8000",
      "token-1",
      "session-1",
    );

    expect(messages[0]?.citations[0]?.documentVersionId).toBe("version-1");
  });

  it("按两阶段协议删除会话", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 202 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteSession("http://localhost:8000", "token-1", "session-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/sessions/session-1/delete",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/sessions/session-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

describe("agent core 接口", () => {
  it("提交限定范围的问题并转换回答证据", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "run-1",
          session_id: "session-1",
          request_id: "request-1",
          mode: "quick",
          status: "completed",
          last_event_seq: 4,
          failure_reason: null,
          step: "persist_answer",
          revision: 3,
          created_at: "2026-10-04T10:00:00Z",
          updated_at: "2026-10-04T10:00:01Z",
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await askAgentQuestion("http://localhost:8000", "token-1", {
      sessionId: "session-1",
      requestId: "request-1",
      question: "模块如何划分？",
      mode: "quick",
      documentIds: ["document-1"],
    });

    expect(result.id).toBe("run-1");
    expect(result.step).toBe("persist_answer");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/agent/questions",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      }),
    );
  });

  it("按序号读取事件并解析载荷", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "event-1",
            run_id: "run-1",
            event_seq: 4,
            event_type: "run.completed",
            payload: "{\"status\":\"completed\"}",
            created_at: "2026-10-04T10:00:00Z",
          },
        ]),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const events = await listAgentRunEvents(
      "http://localhost:8000",
      "token-1",
      "run-1",
      { afterSeq: 3, limit: 20 },
    );

    expect(events[0]?.payload).toEqual({ status: "completed" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/agent/runs/run-1/events?after_seq=3&limit=20",
      expect.any(Object),
    );
  });
});
