import { describe, expect, it } from "vitest";

import { type QuestionInput } from "@yoyo/core";

import { createRunDraftStore } from "./runDraftStore";

class MemoryStorage {
  readonly values = new Map<string, string>();

  get length(): number {
    return this.values.size;
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  key(index: number): string | null {
    return [...this.values.keys()][index] ?? null;
  }
}

const input: QuestionInput = {
  sessionId: "session-1",
  requestId: "request-1",
  question: "比较两个版本的检索设计",
  mode: "comparison",
  topicId: "topic-1",
  tag: "RAG",
  documentIds: ["document-1"],
  versionIds: ["version-1", "version-2"],
};

describe("Run 草稿浏览器适配器", () => {
  it("完整保存和恢复继续运行需要的提问范围", () => {
    const storage = new MemoryStorage();
    const store = createRunDraftStore(storage);

    store.save(input.requestId, input);

    expect(store.load(input.requestId)).toEqual(input);
  });

  it("终态清理后不再返回草稿", () => {
    const storage = new MemoryStorage();
    const store = createRunDraftStore(storage);
    store.save(input.requestId, input);

    store.remove(input.requestId);

    expect(store.load(input.requestId)).toBeNull();
  });

  it("拒绝损坏或 requestId 不一致的缓存内容", () => {
    const storage = new MemoryStorage();
    const store = createRunDraftStore(storage);
    storage.values.set("yoyo.agent-run-draft.v1.request-1", "{broken");
    expect(store.load("request-1")).toBeNull();

    storage.values.set(
      "yoyo.agent-run-draft.v1.request-1",
      JSON.stringify({ ...input, requestId: "another-request" }),
    );
    expect(store.load("request-1")).toBeNull();
  });

  it("注销时只清理本应用的 Run 草稿", () => {
    const storage = new MemoryStorage();
    const store = createRunDraftStore(storage);
    storage.setItem("another.feature", "keep");
    store.save(input.requestId, input);
    store.save("request-2", { ...input, requestId: "request-2" });

    store.clearAll();

    expect(store.load(input.requestId)).toBeNull();
    expect(store.load("request-2")).toBeNull();
    expect(storage.getItem("another.feature")).toBe("keep");
  });
});
