import { describe, expect, it } from "vitest";

import { resolveLoginReturnPath } from "./loginRedirect";

describe("登录完成后的站内回跳", () => {
  it("返回用户登录前准备访问的页面", () => {
    expect(resolveLoginReturnPath({ from: "/documents?tag=ai#latest" })).toBe(
      "/documents?tag=ai#latest",
    );
  });

  it("直接访问登录页时进入默认工作台", () => {
    expect(resolveLoginReturnPath(undefined)).toBe("/workspace");
    expect(resolveLoginReturnPath({ from: "/login" })).toBe("/workspace");
  });

  it("拒绝外部或协议相对回跳地址", () => {
    expect(resolveLoginReturnPath({ from: "https://example.com" })).toBe(
      "/workspace",
    );
    expect(resolveLoginReturnPath({ from: "//example.com" })).toBe(
      "/workspace",
    );
    expect(resolveLoginReturnPath({ from: "/\\example.com" })).toBe(
      "/workspace",
    );
    expect(resolveLoginReturnPath({ from: "/login?next=/documents" })).toBe(
      "/workspace",
    );
  });
});
