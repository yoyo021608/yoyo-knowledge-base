import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildApiUrl,
  getAgentRun,
  importDocument,
  loginAccount,
  requestPasswordReset,
  subscribeUnauthorized,
} from "@yoyo/core";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("web 能引用 core", () => {
  it("按注入的 baseUrl 拼出后端地址", () => {
    expect(buildApiUrl("http://localhost:8000", "health")).toBe("http://localhost:8000/health");
  });
});

describe("账户 core 接口", () => {
  it("把后端登录响应转换成前端领域字段", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            access_token: "token-1",
            expires_at: "2026-09-29T12:00:00Z",
            user: { id: "user-1", email: "alice@example.com" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const session = await loginAccount(
      "http://localhost:8000",
      "alice@example.com",
      "correct-horse-1",
    );

    expect(session.accessToken).toBe("token-1");
    expect(session.user.email).toBe("alice@example.com");
  });

  it("读取本地开发重置凭证但不推断账户存在", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            message: "如果该邮箱存在，密码重置请求已受理",
            development_reset_token: "reset-token",
          }),
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const result = await requestPasswordReset(
      "http://localhost:8000",
      "alice@example.com",
    );

    expect(result.developmentResetToken).toBe("reset-token");
  });
});

describe("文档 core 接口", () => {
  it("只通过 Bearer 身份录入并转换文档字段", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          document_id: "document-1",
          version_id: "version-1",
          index_status: "ready",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await importDocument("http://localhost:8000", "token-1", {
      title: "模块边界",
      content: "documents 负责知识本身。",
      sourceType: "note",
    });

    expect(result.documentId).toBe("document-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/documents/import",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      }),
    );
  });

  it("认证请求返回 401 时统一上报登录失效", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "登录已失效" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const listener = vi.fn();
    const unsubscribe = subscribeUnauthorized(listener);

    try {
      await expect(
        importDocument("http://localhost:8000", "expired-token", {
          title: "过期请求",
          content: "不会被保存",
          sourceType: "note",
        }),
      ).rejects.toThrow("登录已失效");
      expect(listener).toHaveBeenCalledTimes(1);
    } finally {
      unsubscribe();
    }
  });
});

describe("Agent core 接口", () => {
  it("运行请求返回 401 时统一上报登录失效", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "登录已失效" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const listener = vi.fn();
    const unsubscribe = subscribeUnauthorized(listener);

    try {
      await expect(
        getAgentRun("http://localhost:8000", "expired-token", "run-1"),
      ).rejects.toThrow("登录已失效");
      expect(listener).toHaveBeenCalledTimes(1);
    } finally {
      unsubscribe();
    }
  });
});
