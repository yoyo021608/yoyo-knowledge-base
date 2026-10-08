import { type FormEvent, useEffect, useState } from "react";

import {
  confirmPasswordReset,
  loginAccount,
  registerAccount,
  requestPasswordReset,
  type AuthSession,
} from "@yoyo/core";
import { Button } from "@yoyo/ui";

type AccessMode = "login" | "register" | "forgot" | "reset";

interface AccountAccessViewProps {
  apiBaseUrl: string;
  initialMessage?: string;
  onAuthenticated: (session: AuthSession) => void;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "操作失败，请稍后重试";
}

const accessCopy: Record<AccessMode, { description: string; eyebrow: string; title: string }> = {
  login: {
    eyebrow: "WELCOME BACK",
    title: "回到你的知识空间",
    description: "让熟悉的资料与未完成的思考重新展开",
  },
  register: {
    eyebrow: "BEGIN WITH ONE THOUGHT",
    title: "从一份值得留下的内容开始",
    description: "让今天的积累成为明天思考的起点",
  },
  forgot: {
    eyebrow: "FIND YOUR WAY BACK",
    title: "重新找回知识的入口",
    description: "验证邮箱后即可继续保留已建立的知识脉络",
  },
  reset: {
    eyebrow: "A NEW KEY",
    title: "为知识空间设置新的凭证",
    description: "完成重置后使用新密码重新登录",
  },
};

/** 未登录状态下的注册、登录和一次性密码重置流程。 */
export function AccountAccessView({
  apiBaseUrl,
  initialMessage = "",
  onAuthenticated,
}: AccountAccessViewProps) {
  const [mode, setMode] = useState<AccessMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [message, setMessage] = useState(initialMessage);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (initialMessage) setMessage(initialMessage);
  }, [initialMessage]);

  function changeMode(nextMode: AccessMode): void {
    setMode(nextMode);
    setMessage("");
    setPassword("");
    if (nextMode !== "reset") setResetToken("");
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPending(true);
    setMessage("");
    try {
      if (mode === "register") {
        await registerAccount(apiBaseUrl, email, password);
        setMode("login");
        setPassword("");
        setMessage("账户已经创建 使用刚才的邮箱继续登录");
      } else if (mode === "login") {
        const session = await loginAccount(apiBaseUrl, email, password);
        onAuthenticated(session);
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
        setMessage("密码已经更新 使用新密码重新登录");
      }
    } catch (error) {
      setMessage(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  const copy = accessCopy[mode];
  const submitLabel =
    mode === "forgot"
      ? "申请重置"
      : mode === "reset"
        ? "确认重置"
        : mode === "register"
          ? "创建账户"
          : "进入知识空间";

  return (
    <main className="auth-shell">
      <section className="auth-story" aria-label="知识空间介绍">
        <p className="page-eyebrow">A SPACE THAT REMEMBERS</p>
        <h1>让知识有归处<br />让思考有来路</h1>
        <p>每一次阅读 每一个问题<br />都在这里连接成持续生长的知识</p>
        <div className="auth-story-points">
          <div><b>01</b><p><strong>保留来处</strong><small>让观点始终连接原始内容</small></p></div>
          <div><b>02</b><p><strong>延续过程</strong><small>让未完成的探索随时继续</small></p></div>
          <div><b>03</b><p><strong>守住边界</strong><small>让私人知识只属于它的主人</small></p></div>
        </div>
      </section>

      <section className="auth-panel" aria-labelledby="auth-title">
        <header>
          <p className="page-eyebrow">{copy.eyebrow}</p>
          <h2 id="auth-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </header>
        <form className="account-form" onSubmit={(event) => void submit(event)}>
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
                autoComplete="one-time-code"
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
                autoComplete={mode === "login" ? "current-password" : "new-password"}
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
        {message && <p className="auth-message" role="status">{message}</p>}
        <footer className="auth-actions">
          {mode === "login" && (
            <>
              <p>还没有自己的知识空间 <button type="button" onClick={() => changeMode("register")}>创建账户</button></p>
              <button type="button" onClick={() => changeMode("forgot")}>忘记密码</button>
            </>
          )}
          {mode !== "login" && (
            <button type="button" onClick={() => changeMode("login")}>返回登录</button>
          )}
        </footer>
      </section>
    </main>
  );
}
