import type { LoginRedirectState } from "./RequireAuth";

/** 只接受站内绝对路径，避免登录回跳被构造成外部地址。 */
export function resolveLoginReturnPath(state: unknown): string {
  if (typeof state !== "object" || state === null || !("from" in state)) {
    return "/workspace";
  }
  const from = (state as Partial<LoginRedirectState>).from;
  if (
    typeof from !== "string"
    || !from.startsWith("/")
    || from.startsWith("//")
    || from.includes("\\")
    || /[\u0000-\u001f]/u.test(from)
  ) {
    return "/workspace";
  }
  return from.split(/[?#]/u, 1)[0] === "/login" ? "/workspace" : from;
}
