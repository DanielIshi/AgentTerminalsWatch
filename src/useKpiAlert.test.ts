/**
 * R145 TDD — useKpiAlert tests.
 *
 * Tests cover pure logic functions (no React hooks needed for unit tests):
 *   agentsBelow: returns agents whose commit count < threshold
 *   agentsBelow: empty list when all above threshold
 *   agentsBelow: boundary — exactly at threshold is NOT below
 *   agentsBelow: threshold=0 → nobody is below
 *   kpiAlertMessage: single agent below → message contains agent name
 *   kpiAlertMessage: multiple agents → message lists all names
 *   kpiAlertMessage: no agents below → empty string
 *   hasCriticalAlert: true when DEAD agent with 0 commits
 *   hasCriticalAlert: false when all ACTIVE
 *   hasCriticalAlert: true when any agent DEAD
 *   buildKpiSummary: returns answered/total/belowCount
 *   buildKpiSummary: empty agents → zeros
 */

import { agentsBelow, kpiAlertMessage, hasCriticalAlert, buildKpiSummary, shouldFireAlert } from "./useKpiAlert";
import type { AgentInfo } from "./api";

function agent(overrides: Partial<AgentInfo> & { commits?: number } = {}): AgentInfo & { commits: number } {
  return {
    name: "test-agent",
    server: "netcup1",
    state: "ACTIVE",
    technical_state: "running",
    role: "worker",
    session: null,
    commits: 5,
    ...overrides,
  };
}

describe("agentsBelow", () => {
  it("returns agents whose commits < threshold", () => {
    const agents = [agent({ name: "a", commits: 2 }), agent({ name: "b", commits: 10 })];
    expect(agentsBelow(agents, 5).map((a) => a.name)).toEqual(["a"]);
  });

  it("empty list when all above threshold", () => {
    const agents = [agent({ commits: 10 }), agent({ commits: 20 })];
    expect(agentsBelow(agents, 5)).toHaveLength(0);
  });

  it("boundary — exactly at threshold is NOT below", () => {
    const agents = [agent({ commits: 5 })];
    expect(agentsBelow(agents, 5)).toHaveLength(0);
  });

  it("threshold=0 → nobody is below", () => {
    const agents = [agent({ commits: 0 }), agent({ commits: 3 })];
    expect(agentsBelow(agents, 0)).toHaveLength(0);
  });
});

describe("kpiAlertMessage", () => {
  it("single agent below → message contains name", () => {
    const msg = kpiAlertMessage([agent({ name: "ICT" })]);
    expect(msg).toContain("ICT");
  });

  it("multiple agents → message lists all names", () => {
    const msg = kpiAlertMessage([agent({ name: "ICT" }), agent({ name: "Strategy" })]);
    expect(msg).toContain("ICT");
    expect(msg).toContain("Strategy");
  });

  it("no agents → empty string", () => {
    expect(kpiAlertMessage([])).toBe("");
  });
});

describe("hasCriticalAlert", () => {
  it("true when any agent DEAD", () => {
    const agents = [agent({ state: "DEAD" }), agent({ state: "ACTIVE" })];
    expect(hasCriticalAlert(agents)).toBe(true);
  });

  it("false when all ACTIVE", () => {
    const agents = [agent({ state: "ACTIVE" }), agent({ state: "WAITING" })];
    expect(hasCriticalAlert(agents)).toBe(false);
  });

  it("false when empty", () => {
    expect(hasCriticalAlert([])).toBe(false);
  });
});

describe("buildKpiSummary", () => {
  it("returns total and belowCount", () => {
    const agents = [agent({ commits: 2 }), agent({ commits: 10 })];
    const summary = buildKpiSummary(agents, 5);
    expect(summary.total).toBe(2);
    expect(summary.belowCount).toBe(1);
  });

  it("empty agents → zeros", () => {
    const summary = buildKpiSummary([], 5);
    expect(summary.total).toBe(0);
    expect(summary.belowCount).toBe(0);
  });
});

// ── alertFired contract (R145 Bug-Fix: was gated on Notification.permission) ──

describe("shouldFireAlert (alertFired logic)", () => {
  it("fires when belowCount increases from 0 to >0", () => {
    // Pure logic: prevBelow=0, currentBelow=1 → should fire
    expect(shouldFireAlert({ prevBelow: 0, currentBelow: 1, critical: false })).toBe(true);
  });

  it("fires when critical=true regardless of count change", () => {
    expect(shouldFireAlert({ prevBelow: 0, currentBelow: 1, critical: true })).toBe(true);
  });

  it("does NOT fire when belowCount stays the same", () => {
    // Same count: no new degradation → no alert
    expect(shouldFireAlert({ prevBelow: 2, currentBelow: 2, critical: false })).toBe(false);
  });

  it("does NOT fire when belowCount=0", () => {
    expect(shouldFireAlert({ prevBelow: 0, currentBelow: 0, critical: false })).toBe(false);
  });

  it("fires when belowCount increases even without critical", () => {
    expect(shouldFireAlert({ prevBelow: 1, currentBelow: 3, critical: false })).toBe(true);
  });
});

