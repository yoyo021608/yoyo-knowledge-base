import type { WorkspaceQuestionDraft } from "@yoyo/views";

const STORAGE_KEY = "yoyo.workspace-question.v1";
const MODES = new Set(["quick", "research", "comparison", "study"]);

function parseDraft(raw: string | null): WorkspaceQuestionDraft | null {
  if (raw === null) return null;
  try {
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (typeof value.question !== "string" || !value.question.trim() || !MODES.has(String(value.mode))) {
      return null;
    }
    return value as unknown as WorkspaceQuestionDraft;
  } catch {
    return null;
  }
}

/** 工作台只交接一次提问草稿；会话页读取后立即清理，避免覆盖后续输入。 */
export const browserWorkspaceDraftStore = {
  save(draft: WorkspaceQuestionDraft): void {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  },
  consume(): WorkspaceQuestionDraft | null {
    const draft = parseDraft(window.sessionStorage.getItem(STORAGE_KEY));
    window.sessionStorage.removeItem(STORAGE_KEY);
    return draft;
  },
  clear(): void {
    window.sessionStorage.removeItem(STORAGE_KEY);
  },
};
