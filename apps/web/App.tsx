import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomeView } from "@yoyo/views";

export function App() {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomeView apiBaseUrl={apiBaseUrl} />} />
      </Routes>
    </BrowserRouter>
  );
}
