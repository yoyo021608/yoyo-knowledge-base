import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApiUrl, loginAccount, requestPasswordReset } from "@yoyo/core";

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
