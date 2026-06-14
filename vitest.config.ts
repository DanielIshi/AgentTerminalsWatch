import { defineConfig } from "vitest/config";

// RAM-Krise 2026-06-14 (hostinger Load 100, 5 vitest-Zombies ~6.7 GB).
// Worker-Pool-Limit verhindert, dass parallele Runs (z.B. zwei Worker
// gleichzeitig `npm run test:watch` lassen oder Test-Run hängen bleibt)
// mehr als 2 Threads gleichzeitig spawnen. Auf 16 GB VPS reicht das fuer
// die Suite und verhindert Memory-Pressure-Kaskade.
// Reference: GH#362 (closed), Notion-Audit-Task 37f5154b-eb42-8123-b1bd-c92cc12ba923.

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "tests/**/*.test.ts"],
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
