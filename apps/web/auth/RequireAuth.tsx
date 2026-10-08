import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import type { AuthStatus } from "../useAuthSession";

interface RequireAuthProps {
  accessToken: string | null;
  children: ReactNode | ((accessToken: string) => ReactNode);
  error?: string;
  onRetry: () => void;
  status: AuthStatus;
}

export interface LoginRedirectState {
  from: string;
}

/** 统一保护需要身份的页面，并记录登录完成后应当返回的位置。 */
export function RequireAuth({
  accessToken,
  children,
  error = "",
  onRetry,
  status,
}: RequireAuthProps) {
  const location = useLocation();

  if (status === "checking") {
    return <main className="auth-gate" aria-busy="true"><p>正在恢复登录状态…</p></main>;
  }

  if (status === "unavailable") {
    return (
      <main className="auth-gate" role="alert">
        <p>{error || "暂时无法确认登录状态"}</p>
        <button onClick={onRetry} type="button">重新检查</button>
      </main>
    );
  }

  if (status === "anonymous" || accessToken === null) {
    const from = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate replace state={{ from } satisfies LoginRedirectState} to="/login" />;
  }

  return typeof children === "function" ? children(accessToken) : children;
}
