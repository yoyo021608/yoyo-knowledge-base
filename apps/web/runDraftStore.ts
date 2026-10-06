import { type QuestionInput } from "@yoyo/core";
import { type RunDraftStore } from "@yoyo/views";

const KEY_PREFIX = "yoyo.agent-run-draft.v1.";
const MODES = new Set(["quick", "research", "comparison", "study"]);

interface StoragePort {
  readonly length: number;
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
  key(index: number): string | null;
}

export interface ManagedRunDraftStore extends RunDraftStore {
  clearAll(): void;
}

function isOptionalString(value: unknown): value is string | undefined {
  return value === undefined || typeof value === "string";
}

function isOptionalStringArray(value: unknown): value is string[] | undefined {
  return value === undefined
    || (Array.isArray(value) && value.every((item) => typeof item === "string"));
}

/** 只恢复本应用写入的完整提问参数，损坏或被篡改的数据不能进入 Agent。 */
function questionInputOf(value: unknown): QuestionInput | null {
  if (typeof value !== "object" || value === null) return null;
  const input = value as Record<string, unknown>;
  if (
    typeof input.sessionId !== "string"
    || !input.sessionId
    || typeof input.requestId !== "string"
    || !input.requestId
    || typeof input.question !== "string"
    || !input.question.trim()
    || (input.mode !== undefined && !MODES.has(String(input.mode)))
    || !isOptionalString(input.topicId)
    || !isOptionalString(input.tag)
    || !isOptionalString(input.userAnswer)
    || !isOptionalStringArray(input.documentIds)
    || !isOptionalStringArray(input.versionIds)
  ) {
    return null;
  }
  return input as unknown as QuestionInput;
}

/** apps/web 的浏览器适配器；views 仍只依赖抽象的 RunDraftStore。 */
export function createRunDraftStore(storage: StoragePort): ManagedRunDraftStore {
  return {
    load(requestId) {
      const key = `${KEY_PREFIX}${requestId}`;
      const raw = storage.getItem(key);
      if (raw === null) return null;
      try {
        const input = questionInputOf(JSON.parse(raw) as unknown);
        if (input?.requestId === requestId) return input;
      } catch {
        // JSON 损坏时按不存在处理，并清理无效草稿。
      }
      storage.removeItem(key);
      return null;
    },
    save(requestId, input) {
      if (input.requestId !== requestId) {
        throw new Error("Run 草稿的 requestId 不一致");
      }
      storage.setItem(`${KEY_PREFIX}${requestId}`, JSON.stringify(input));
    },
    remove(requestId) {
      storage.removeItem(`${KEY_PREFIX}${requestId}`);
    },
    clearAll() {
      const keys: string[] = [];
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        if (key?.startsWith(KEY_PREFIX)) keys.push(key);
      }
      keys.forEach((key) => storage.removeItem(key));
    },
  };
}

/** 延迟取得 sessionStorage；浏览器禁用存储时由 useRunRecovery 回退到内存。 */
export const browserRunDraftStore = createRunDraftStore({
  get length() {
    return window.sessionStorage.length;
  },
  getItem: (key) => window.sessionStorage.getItem(key),
  setItem: (key, value) => window.sessionStorage.setItem(key, value),
  removeItem: (key) => window.sessionStorage.removeItem(key),
  key: (index) => window.sessionStorage.key(index),
});
