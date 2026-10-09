import type { Page, Route } from "@playwright/test";

const NOW = "2026-10-09T08:00:00Z";

interface MockState {
  documents: Record<string, unknown>[];
  messages: Record<string, unknown>[];
  sessions: Record<string, unknown>[];
}

function respond(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: "application/json",
    headers: {
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
      "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
      "Access-Control-Allow-Origin": "*",
    },
    body: body === undefined ? "" : JSON.stringify(body),
  });
}

/**
 * 浏览器验收只替换 HTTP 边界，页面路由、状态恢复、表单和视图组合仍使用正式代码。
 * 后端领域协作由 tests/e2e/test_mvp_flow.py 独立验证，避免浏览器测试重复业务实现。
 */
export async function installMockApi(page: Page): Promise<MockState> {
  const state: MockState = { documents: [], messages: [], sessions: [] };
  const documentVersion = {
    id: "version-1",
    document_id: "document-1",
    version: 1,
    title_snapshot: "可恢复知识问答",
    content_snapshot: "回答引用绑定具体文档版本，刷新后仍能恢复历史依据。",
    index_status: "ready",
    index_error: null,
    source: {
      version_id: "version-1",
      content: "回答引用绑定具体文档版本，刷新后仍能恢复历史依据。",
      source_type: "note",
      source_url: null,
      title: "可恢复知识问答",
      captured_at: NOW,
    },
    created_at: NOW,
  };
  const run = {
    id: "run-1",
    session_id: "session-1",
    request_id: "browser-request-1",
    mode: "quick",
    status: "completed",
    last_event_seq: 2,
    failure_reason: null,
    step: "persist_answer",
    revision: 5,
    created_at: NOW,
    updated_at: NOW,
  };

  await page.route("http://localhost:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const method = request.method();

    if (method === "OPTIONS") {
      await respond(route, undefined, 204);
      return;
    }
    if (method === "POST" && pathname === "/api/users/register") {
      await respond(route, { id: "user-1", email: "alice@example.com" }, 201);
      return;
    }
    if (method === "POST" && pathname === "/api/auth/login") {
      await respond(route, {
        access_token: "browser-token",
        expires_at: "2026-10-09T09:00:00Z",
        user: { id: "user-1", email: "alice@example.com" },
      });
      return;
    }
    if (method === "GET" && pathname === "/api/users/me") {
      await respond(route, { id: "user-1", email: "alice@example.com" });
      return;
    }
    if (method === "GET" && pathname === "/api/topics") {
      await respond(route, []);
      return;
    }
    if (method === "GET" && pathname === "/api/tags") {
      await respond(route, []);
      return;
    }
    if (method === "POST" && pathname === "/api/documents/import") {
      state.documents = [
        {
          id: "document-1",
          topic_id: null,
          title: "可恢复知识问答",
          status: "active",
          is_favorite: false,
          current_version: 1,
          current_version_id: "version-1",
          index_status: "ready",
          tags: [],
          created_at: NOW,
          updated_at: NOW,
        },
      ];
      await respond(
        route,
        { document_id: "document-1", version_id: "version-1", index_status: "ready" },
        201,
      );
      return;
    }
    if (method === "GET" && pathname === "/api/documents") {
      const status = url.searchParams.get("status");
      await respond(
        route,
        state.documents.filter((document) => status === null || document.status === status),
      );
      return;
    }
    if (method === "GET" && pathname === "/api/documents/document-1") {
      await respond(route, { document: state.documents[0], version: documentVersion });
      return;
    }
    if (method === "GET" && pathname === "/api/documents/document-1/versions") {
      await respond(route, [documentVersion]);
      return;
    }
    if (method === "GET" && pathname === "/api/documents/document-1/relations") {
      await respond(route, []);
      return;
    }
    if (method === "GET" && pathname === "/api/documents/document-1/knowledge") {
      await respond(route, {
        document_id: "document-1",
        version_id: "version-1",
        points: [],
        entities: [],
        relations: [],
      });
      return;
    }
    if (method === "POST" && pathname === "/api/sessions") {
      const body = request.postDataJSON() as { name: string };
      state.sessions = [
        {
          id: "session-1",
          user_id: "user-1",
          name: body.name,
          status: "active",
          active_run_id: null,
          created_at: NOW,
          updated_at: NOW,
        },
      ];
      await respond(route, state.sessions[0], 201);
      return;
    }
    if (method === "GET" && pathname === "/api/sessions") {
      await respond(route, state.sessions);
      return;
    }
    if (method === "GET" && pathname === "/api/sessions/session-1/messages") {
      await respond(route, state.messages);
      return;
    }
    if (
      method === "GET" &&
      [
        "/api/sessions/session-1/results",
        "/api/sessions/session-1/practice",
        "/api/sessions/session-1/feedback",
      ].includes(pathname)
    ) {
      await respond(route, []);
      return;
    }
    if (method === "POST" && pathname === "/api/agent/questions") {
      const body = request.postDataJSON() as { question: string; request_id: string };
      run.request_id = body.request_id;
      state.messages = [
        {
          id: "message-user-1",
          session_id: "session-1",
          run_id: "run-1",
          role: "user",
          content: body.question,
          citations: [],
          created_at: NOW,
        },
        {
          id: "message-assistant-1",
          session_id: "session-1",
          run_id: "run-1",
          role: "assistant",
          content: "回答会保留具体版本与原文依据。",
          citations: [
            {
              id: "citation-1",
              message_id: "message-assistant-1",
              document_id: "document-1",
              document_version_id: "version-1",
              chunk_id: "chunk-1",
              title_snapshot: "可恢复知识问答",
              quote: "回答引用绑定具体文档版本",
              source_url: null,
            },
          ],
          created_at: NOW,
        },
      ];
      await respond(route, run, 202);
      return;
    }
    if (method === "GET" && pathname === "/api/agent/runs/run-1") {
      await respond(route, run);
      return;
    }
    if (method === "GET" && pathname === "/api/agent/runs/run-1/events") {
      await respond(route, [
        {
          id: "event-1",
          run_id: "run-1",
          event_seq: 1,
          event_type: "run.created",
          payload: "{}",
          created_at: NOW,
        },
        {
          id: "event-2",
          run_id: "run-1",
          event_seq: 2,
          event_type: "run.completed",
          payload: "{}",
          created_at: NOW,
        },
      ]);
      return;
    }

    await respond(route, { detail: `浏览器测试没有定义 ${method} ${pathname}` }, 501);
  });

  return state;
}
