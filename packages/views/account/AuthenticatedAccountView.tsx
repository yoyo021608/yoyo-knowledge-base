import { type FormEvent, useState } from "react";

import {
  changeAccountPassword,
  logoutAccount,
  type UserProfile,
} from "@yoyo/core";
import { Button } from "@yoyo/ui";

import { passwordRequirement, strongPasswordPattern } from "./passwordPolicy";

interface AuthenticatedAccountViewProps {
  apiBaseUrl: string;
  accessToken: string;
  onSignedOut: (notice: string) => void;
  onRetryProfile: () => void;
  profile: UserProfile | null;
  profileError: string;
}

function messageOf(error: unknown): string {
  if (error instanceof TypeError) return "暂时无法连接服务，请稍后重试";
  return error instanceof Error ? error.message : "操作失败，请稍后重试";
}

/** 登录状态下的身份展示、修改密码和注销流程。 */
export function AuthenticatedAccountView({
  apiBaseUrl,
  accessToken,
  onSignedOut,
  onRetryProfile,
  profile,
  profileError,
}: AuthenticatedAccountViewProps) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [passwordPending, setPasswordPending] = useState(false);
  const [signOutPending, setSignOutPending] = useState(false);

  async function signOut(): Promise<void> {
    setSignOutPending(true);
    let notice = "已退出当前设备";
    try {
      await logoutAccount(apiBaseUrl, accessToken);
      notice = "已安全退出";
    } catch {
      // 服务不可达时仍删除本地凭证，但不宣称远端会话已经撤销。
    } finally {
      onSignedOut(notice);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPasswordPending(true);
    setMessage("");
    try {
      await changeAccountPassword(apiBaseUrl, accessToken, oldPassword, newPassword);
      onSignedOut("密码已更新，请重新登录");
    } catch (error) {
      setMessage(messageOf(error));
    } finally {
      setPasswordPending(false);
    }
  }

  return (
    <main className="account-shell">
      <header className="account-heading">
        <p className="page-eyebrow">ACCOUNT & SECURITY</p>
        <h1>让知识始终只属于你</h1>
        <p>在这里管理身份与安全 设置变化不会影响已经积累的内容</p>
      </header>

      <section className="account-settings-grid">
        <article className="account-identity-card">
          <span className="account-avatar" aria-hidden="true">{profile?.email.slice(0, 1).toUpperCase() ?? "·"}</span>
          <div>
            <p>当前身份</p>
            <h2>{profile?.email ?? "正在读取身份"}</h2>
            <small>你的文档 会话与研究记录都与此身份相连</small>
          </div>
          <span className="account-state"><i /> 已安全登录</span>
        </article>

        <article className="account-security-card">
          <header>
            <span aria-hidden="true">◇</span>
            <div><h2>更新登录密码</h2><p>修改后所有已有登录都会退出</p></div>
          </header>
          <form className="account-form" onSubmit={(event) => void changePassword(event)}>
            <label>
              当前密码
              <input
                type="password"
                autoComplete="current-password"
                required
                value={oldPassword}
                onChange={(event) => setOldPassword(event.target.value)}
              />
            </label>
            <label>
              新密码
              <input
                type="password"
                autoComplete="new-password"
                minLength={10}
                maxLength={128}
                pattern={strongPasswordPattern}
                title={passwordRequirement}
                aria-describedby="new-password-requirement"
                required
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
              <small className="field-hint" id="new-password-requirement">
                {passwordRequirement}
              </small>
            </label>
            <Button type="submit" disabled={passwordPending}>{passwordPending ? "正在更新…" : "更新密码"}</Button>
          </form>
        </article>

        <article className="account-session-card">
          <div><h2>结束当前登录</h2><p>离开共用设备前 请安全退出当前账户</p></div>
          <Button disabled={signOutPending} onClick={() => void signOut()}>{signOutPending ? "正在退出…" : "退出登录"}</Button>
        </article>
      </section>
      {profileError && (
        <p className="auth-message account-message" data-kind="error" role="alert">
          {profileError} <button type="button" onClick={onRetryProfile}>重新读取</button>
        </p>
      )}
      {message && <p className="auth-message account-message" data-kind="error" role="alert">{message}</p>}
    </main>
  );
}
