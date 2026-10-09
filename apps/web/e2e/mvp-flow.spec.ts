import { expect, test } from "@playwright/test";

import { installMockApi } from "./support/mockApi";

test("用户可以从注册进入带版本引用的知识问答", async ({ page }) => {
  await installMockApi(page);

  await page.goto("/documents");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByRole("button", { name: "创建账户" }).click();
  await page.getByLabel("邮箱").fill("alice@example.com");
  await page.getByLabel("密码").fill("correct-horse-1");
  await page.getByRole("button", { name: "创建账户" }).click();
  await expect(page.getByRole("status")).toContainText("账户已经创建");

  await page.getByLabel("密码").fill("correct-horse-1");
  await page.getByRole("button", { name: "进入知识空间" }).click();
  await expect(page).toHaveURL(/\/documents$/);
  await expect(page.getByRole("heading", { name: "个人知识库" })).toBeVisible();

  await page.getByLabel("标题").fill("可恢复知识问答");
  await page.getByLabel(/^正文/).fill("回答引用绑定具体文档版本，刷新后仍能恢复历史依据。");
  await page.getByRole("button", { name: "录入并建立索引" }).click();
  await expect(page.getByRole("status")).toContainText("索引状态：ready");
  await expect(page.getByRole("button", { name: /可恢复知识问答/ })).toBeVisible();

  await page.getByRole("link", { name: "知识问答" }).click();
  await expect(page).toHaveURL(/\/sessions$/);
  await page.getByLabel("新会话名称").fill("版本追溯研究");
  await page.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByText("版本追溯研究", { exact: true })).toBeVisible();

  await page.getByLabel("问题").fill("回答如何保留历史依据");
  await page.getByRole("button", { name: "开始", exact: true }).click();
  await expect(page.getByText("回答会保留具体版本与原文依据。")).toBeVisible();
  await expect(page.getByText(/状态：\s*已完成\s*·\s*保存回答/)).toBeVisible();

  await page.getByText("引用（1）").click();
  await expect(page.getByText("回答引用绑定具体文档版本")).toBeVisible();
  await expect(page.getByText("版本 version-1 · 片段 chunk-1")).toBeVisible();

  await page.reload();
  await expect(page.getByText("回答会保留具体版本与原文依据。")).toBeVisible();
  await expect(page.getByText("版本追溯研究", { exact: true })).toBeVisible();
});
