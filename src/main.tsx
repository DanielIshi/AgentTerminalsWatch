import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initSentry } from "./sentry";

// M2: no-op if VITE_SENTRY_DSN is not set (zero cost)
initSentry({
  dsn: (import.meta as any).env?.VITE_SENTRY_DSN,
  environment: (import.meta as any).env?.MODE,
  release: (import.meta as any).env?.VITE_APP_VERSION,
});

const root = document.getElementById("root");
if (!root) throw new Error("No #root element found");
createRoot(root).render(<App />);
