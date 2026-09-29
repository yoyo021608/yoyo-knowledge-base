import { type FormEvent, useEffect, useState } from "react";

import {
  changeAccountPassword,
  fetchCurrentUser,
  logoutAccount,
  type UserProfile,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface AuthenticatedAccountViewProps {
  apiBaseUrl: string;
  accessToken: string;
  onSignedOut: () => void;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "操作失败，请稍后重试";
}

/** 登录状态下的身份展示、修改密码和注销流程。 */
export function AuthenticatedAccountView({
  apiBaseUrl,
  accessToken,
  onSignedOut,
}: AuthenticatedAccountViewProps) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("正在读取身份…");

  useEffect(() => {
    let active = true;
    void fetchCurrentUser(apiBaseUrl, accessToken)
      .then((user) => {
        if (active) {
          setProfile(user);
          setMessage("");
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setMessage(messageOf(error));
          onSignedOut();
        }
      });
    return () => {
      active = false;
    };
  }, [accessToken, apiBaseUrl, onSignedOut]);

  async function signOut(): Promise<void> {
    try {
      await logoutAccount(apiBaseUrl, accessToken);
    } finally {
      onSignedOut();
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      await changeAccountPassword(
        apiBaseUrl,
        accessToken,
        oldPassword,
        newPassword,
      );
      onSignedOut();
    } catch (error) {
      setMessage(messageOf(error));
    }
  }

  return (
    <main className="page-shell">
      <Card>
        <h1>账户</h1>
        {profile && <p>当前用户：{profile.email}</p>}
        {message && <p role="status">{message}</p>}
        <Button onClick={() => void signOut()}>注销当前登录</Button>
        <h2>修改密码</h2>
        <form
          className="account-form"
          onSubmit={(event) => void changePassword(event)}
        >
          <label>
            原密码
            <input
              type="password"
              required
              value={oldPassword}
              onChange={(event) => setOldPassword(event.target.value)}
            />
          </label>
          <label>
            新密码
            <input
              type="password"
              minLength={10}
              maxLength={128}
              required
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </label>
          <Button type="submit">修改并退出全部登录</Button>
        </form>
      </Card>
    </main>
  );
}
