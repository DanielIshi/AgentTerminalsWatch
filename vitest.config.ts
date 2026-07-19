import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// RAM-Krise 2026-06-14 (hostinger Load 100, 5 vitest-Zombies ~6.7 GB).
// Worker-Pool-Limit verhindert, dass parallele Runs (z.B. zwei Worker
// gleichzeitig `npm run test:watch` lassen oder Test-Run hängen bleibt)
// mehr als 2 Threads gleichzeitig spawnen. Auf 16 GB VPS reicht das fuer
// die Suite und verhindert Memory-Pressure-Kaskade.
// Reference: GH#362 (closed), Notion-Audit-Task 37f5154b-eb42-8123-b1bd-c92cc12ba923.
//
// GH#709 (2026-07-19): react plugin + tsx support added for §312j PaymentButton tests.
// include extended to cover *.spec.tsx (jsdom-based React component tests).

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    include: [
      "src/**/*.test.ts",
      "src/**/*.test.tsx",
      "tests/**/*.test.ts",
      "tests/**/*.test.tsx",
      "tests/**/*.spec.tsx",
    ],
    globals: true,
    pool: "threads",
    poolOptions: {
      threads: {
        minThreads: 1,
        maxThreads: 2,
      },
    },
    maxConcurrency: 4,
  },
});
