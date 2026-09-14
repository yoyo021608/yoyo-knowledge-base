import { describe, expect, it } from "vitest";

import { buildApiUrl } from "@yoyo/core";

describe("web 能引用 core", () => {
  it("按注入的 baseUrl 拼出后端地址", () => {
    expect(buildApiUrl("http://localhost:8000", "health")).toBe("http://localhost:8000/health");
  });
});
