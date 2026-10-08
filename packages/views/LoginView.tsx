import { AccountAccessView } from "./account/AccountAccessView";
import type { AuthSession } from "@yoyo/core";

interface LoginViewProps {
  apiBaseUrl: string;
  notice?: string;
  onAuthenticated: (session: AuthSession) => void;
}

/** 登录入口只负责身份建立、注册与密码找回，不承载登录后的账户管理。 */
export function LoginView({ apiBaseUrl, notice = "", onAuthenticated }: LoginViewProps) {
  return (
    <AccountAccessView
      apiBaseUrl={apiBaseUrl}
      initialMessage={notice}
      onAuthenticated={onAuthenticated}
    />
  );
}
