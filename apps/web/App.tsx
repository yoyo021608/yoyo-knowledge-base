import { useCallback, useState } from "react";
import { BrowserRouter, Route, Routes, useNavigate } from "react-router-dom";

import {
  AccountView,
  DocumentsView,
  HomeView,
  NotFoundView,
  SessionsView,
  WorkspaceView,
} from "@yoyo/views";

import { AppNavigation } from "./AppNavigation";
import { RouteLink } from "./RouteLink";
import { LoginRoute } from "./auth/LoginRoute";
import { RequireAuth } from "./auth/RequireAuth";
import { browserRunDraftStore } from "./runDraftStore";
import { useAuthSession } from "./useAuthSession";
import { browserWorkspaceDraftStore } from "./workspaceDraftStore";

interface SessionsRouteProps {
  accessToken: string;
  apiBaseUrl: string;
}

function SessionsRoute({ accessToken, apiBaseUrl }: SessionsRouteProps) {
  const [initialQuestion] = useState(() => {
    try {
      return browserWorkspaceDraftStore.consume();
    } catch {
      return null;
    }
  });

  return (
    <SessionsView
      apiBaseUrl={apiBaseUrl}
      accessToken={accessToken}
      initialQuestion={initialQuestion}
      runDraftStore={browserRunDraftStore}
    />
  );
}

function Application() {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const auth = useAuthSession(apiBaseUrl);
  const navigate = useNavigate();
  const [navigationCollapsed, setNavigationCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem("yoyo.navigation.collapsed") === "true";
    } catch {
      return false;
    }
  });

  function changeNavigationCollapsed(collapsed: boolean): void {
    setNavigationCollapsed(collapsed);
    try {
      window.localStorage.setItem("yoyo.navigation.collapsed", String(collapsed));
    } catch {
      // 浏览器禁止存储时仍保留本次页面中的收缩状态。
    }
  }

  const signOut = useCallback((): void => {
    try {
      browserRunDraftStore.clearAll();
      browserWorkspaceDraftStore.clear();
    } catch {
      // 浏览器存储异常不能阻止当前页面撤销登录状态。
    }
    auth.clear();
  }, [auth.clear]);

  return (
      <div className={`app-shell${navigationCollapsed ? " sidebar-collapsed" : ""}`}>
        <AppNavigation
          collapsed={navigationCollapsed}
          isAuthenticated={auth.status === "authenticated"}
          onCollapsedChange={changeNavigationCollapsed}
        />
        <div className="app-content">
          <Routes>
            <Route
              path="/"
              element={<HomeView isAuthenticated={auth.status === "authenticated"} LinkComponent={RouteLink} />}
            />
            <Route
              path="/login"
              element={
                <LoginRoute
                  accessToken={auth.accessToken}
                  apiBaseUrl={apiBaseUrl}
                  notice={auth.notice}
                  onAuthenticated={auth.authenticate}
                  status={auth.status}
                />
              }
            />
            <Route
              path="/workspace"
              element={
                <RequireAuth
                  accessToken={auth.accessToken}
                  error={auth.profileError}
                  onRetry={() => void auth.refreshProfile()}
                  status={auth.status}
                >
                  <WorkspaceView
                    LinkComponent={RouteLink}
                    onStartResearch={(draft) => {
                      try {
                        browserWorkspaceDraftStore.save(draft);
                      } catch {
                        // 存储不可用时仍允许进入会话页，用户可在会话页重新输入。
                      }
                      navigate("/sessions");
                    }}
                  />
                </RequireAuth>
              }
            />
            <Route
              path="/account"
              element={
                <RequireAuth
                  accessToken={auth.accessToken}
                  error={auth.profileError}
                  onRetry={() => void auth.refreshProfile()}
                  status={auth.status}
                >
                  {(accessToken) => (
                    <AccountView
                      apiBaseUrl={apiBaseUrl}
                      accessToken={accessToken}
                      onSignedOut={signOut}
                      profile={auth.profile}
                      profileError={auth.profileError}
                      onRetryProfile={() => void auth.refreshProfile()}
                    />
                  )}
                </RequireAuth>
              }
            />
            <Route
              path="/documents"
              element={
                <RequireAuth
                  accessToken={auth.accessToken}
                  error={auth.profileError}
                  onRetry={() => void auth.refreshProfile()}
                  status={auth.status}
                >
                  {(accessToken) => (
                    <DocumentsView
                      apiBaseUrl={apiBaseUrl}
                      accessToken={accessToken}
                    />
                  )}
                </RequireAuth>
              }
            />
            <Route
              path="/sessions"
              element={
                <RequireAuth
                  accessToken={auth.accessToken}
                  error={auth.profileError}
                  onRetry={() => void auth.refreshProfile()}
                  status={auth.status}
                >
                  {(accessToken) => (
                    <SessionsRoute apiBaseUrl={apiBaseUrl} accessToken={accessToken} />
                  )}
                </RequireAuth>
              }
            />
            <Route path="*" element={<NotFoundView LinkComponent={RouteLink} />} />
          </Routes>
        </div>
      </div>
  );
}

export function App() {
  return <BrowserRouter><Application /></BrowserRouter>;
}
