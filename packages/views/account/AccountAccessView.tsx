import { type FormEvent, useState } from "react";

import {
  confirmPasswordReset,
  loginAccount,
  registerAccount,
  requestPasswordReset,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

type AccessMode = "login" | "register" | "forgot" | "reset";

interface AccountAccessViewProps {
  apiBaseUrl: string;
  onAuthenticated: (accessToken: string) => void;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "操作失败，请稍后重试";
}

/** 未登录状态下的注册、登录和一次性密码重置流程。 */
export function AccountAccessView({
  apiBaseUrl,
  onAuthenticated,
}: AccountAccessViewProps) {
  const [mode, setMode] = useState<AccessMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPending(true);
    setMessage("");
    try {
      if (mode === "register") {
        await registerAccount(apiBaseUrl, email, password);
        setMode("login");
        setPassword("");
        setMessage("注册成功，请登录");
      } else if (mode === "login") {
        const session = await loginAccount(apiBaseUrl, email, password);
        onAuthenticated(session.accessToken);
      } else if (mode === "forgot") {
        const result = await requestPasswordReset(apiBaseUrl, email);
        setMessage(result.message);
        if (result.developmentResetToken !== null) {
          setResetToken(result.developmentResetToken);
          setMode("reset");
        }
      } else {
        await confirmPasswordReset(apiBaseUrl, resetToken, password);
        setMode("login");
        setPassword("");
        setResetToken("");
        setMessage("密码已重置，请重新登录");
      }
    } catch (error) {
      setMessage(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  const title =
    mode === "register"
      ? "注册账户"
      : mode === "login"
        ? "登录"
        : "找回密码";
  const submitLabel =
    mode === "forgot"
      ? "申请重置"
      : mode === "reset"
        ? "确认重置"
        : mode === "register"
          ? "注册"
          : "登录";

  return (
    <main className="page-shell">
      <Card>
        <h1>{title}</h1>
        <p className="muted">
          账户模块只确认你的身份，资料权限由各业务模块判断。
        </p>
        <form
          className="account-form"
          onSubmit={(event) => void submit(event)}
        >
          {mode !== "reset" && (
            <label>
              邮箱
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
          )}
          {mode === "reset" && (
            <label>
              一次性重置凭证
              <input
                type="text"
                required
                value={resetToken}
                onChange={(event) => setResetToken(event.target.value)}
              />
            </label>
          )}
          {mode !== "forgot" && (
            <label>
              {mode === "reset" ? "新密码" : "密码"}
              <input
                type="password"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                minLength={mode === "login" ? 1 : 10}
                maxLength={128}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
          )}
          <Button type="submit" disabled={pending}>
            {pending ? "处理中…" : submitLabel}
          </Button>
        </form>
        {message && <p role="status">{message}</p>}
        <div className="account-actions">
          <Button
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "创建账户" : "返回登录"}
          </Button>
          {mode === "login" && (
            <Button onClick={() => setMode("forgot")}>忘记密码</Button>
          )}
        </div>
      </Card>
    </main>
  );
}
