import { LoginView } from "@yoyo/views";
import type { AuthSession } from "@yoyo/core";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { resolveLoginReturnPath } from "./loginRedirect";
import type { AuthStatus } from "../useAuthSession";

interface LoginRouteProps {
  accessToken: string | null;
  apiBaseUrl: string;
  notice?: string;
  onAuthenticated: (session: AuthSession) => void;
  status: AuthStatus;
}

/** 登录页建立身份后返回原目标；已有身份时直接前往目标页面。 */
export function LoginRoute({
  accessToken,
  apiBaseUrl,
  notice = "",
  onAuthenticated,
  status,
}: LoginRouteProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const returnPath = resolveLoginReturnPath(location.state);

  if (status === "checking") {
    return <main className="auth-gate" aria-busy="true"><p>正在恢复登录状态…</p></main>;
  }

  if (status === "authenticated" && accessToken !== null) {
    return <Navigate replace to={returnPath} />;
  }

  return (
    <LoginView
      apiBaseUrl={apiBaseUrl}
      notice={notice}
      onAuthenticated={(session) => {
        onAuthenticated(session);
        navigate(returnPath, { replace: true });
      }}
    />
  );
}
