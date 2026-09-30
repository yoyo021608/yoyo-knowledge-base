import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { AccountView, DocumentsView, HomeView } from "@yoyo/views";

import { useAuthSession } from "./useAuthSession";

export function App() {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const auth = useAuthSession();

  return (
    <BrowserRouter>
      <nav className="app-nav" aria-label="主导航">
        <Link to="/">首页</Link>
        <Link to="/account">账户</Link>
        <Link to="/documents">知识库</Link>
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
              onSignedOut={auth.clear}
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
      </Routes>
    </BrowserRouter>
  );
}
