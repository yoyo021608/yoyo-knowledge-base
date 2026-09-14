import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@yoyo/ui/styles/global.css";

import { App } from "./App";

const container = document.getElementById("root");

if (container === null) {
  throw new Error("找不到 #root 容器，index.html 可能被改动过");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
