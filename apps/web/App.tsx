import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { AccountView, DocumentsView, HomeView, SessionsView } from "@yoyo/views";

import { browserRunDraftStore } from "./runDraftStore";
import { useAuthSession } from "./useAuthSession";

export function App() {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const auth = useAuthSession();

  function signOut(): void {
    try {
      browserRunDraftStore.clearAll();
    } catch {
      // 浏览器存储异常不能阻止当前页面撤销登录状态。
    }
    auth.clear();
  }

  return (
    <BrowserRouter>
      <nav className="app-nav" aria-label="主导航">
        <Link to="/">首页</Link>
        <Link to="/account">账户</Link>
        <Link to="/documents">知识库</Link>
        <Link to="/sessions">知识问答</Link>
      </nav>
      <Routes>
        <Route path="/" element={<HomeView apiBaseUrl={apiBaseUrl} />} />
        <Route
          path="/account"
          element={
            <AccountView
              apiBaseUrl={apiBaseUrl}
              accessToken={auth.accessToken}
              onAuthenticated={auth.authenticate}
              onSignedOut={signOut}
            />
          }
        />
        <Route
          path="/documents"
          element={
            <DocumentsView
              apiBaseUrl={apiBaseUrl}
              accessToken={auth.accessToken}
            />
          }
        />
        <Route
          path="/sessions"
          element={
            <SessionsView
              apiBaseUrl={apiBaseUrl}
              accessToken={auth.accessToken}
              runDraftStore={browserRunDraftStore}
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
