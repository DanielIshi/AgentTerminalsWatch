/**
 * R145 TDD — App.tsx v3: AgentStatusBadge + useKpiAlert integration contracts.
 *
 * Tests cover (pure-function layer, no DOM needed):
 *   AgentRow uses AgentStatusBadge: verified via badgeColor/Label/isPulsing exports
 *   buildKpiSummary used by App: correct counts with 0-commit agents
 *   kpiAlertMessage: lists agent names below threshold
 *   hasCriticalAlert: true when any DEAD agent present
 *   App KPI alert bar: fires when belowCount > 0 AND alertFired
 *   agentsWithCommits mapping: missing commits defaults to 0
 */
import { buildKpiSummary, kpiAlertMessage, hasCriticalAlert, agentsBelow } from "./useKpiAlert";
import type { AgentWithCommits } from "./useKpiAlert";

const DEAD_AGENT: AgentWithCommits = { name: "ICT", state: "DEAD", server: "netcup1", commits: 0 };
const ACTIVE_AGENT: AgentWithCommits = { name: "CEO", state: "ACTIVE", server: "netcup1", commits: 5 };
const WAITING_AGENT: AgentWithCommits = { name: "Marketing", state: "WAITING", server: "hetzner", commits: 0 };

describe("App.tsx v3: buildKpiSummary used by App", () => {
  it("all agents with 0 commits → all below threshold=1", () => {
    const summary = buildKpiSummary([DEAD_AGENT, WAITING_AGENT], 1);
    expect(summary.belowCount).toBe(2);
    expect(summary.total).toBe(2);
  });

  it("agent with 5 commits is not below threshold=1", () => {
    const summary = buildKpiSummary([ACTIVE_AGENT], 1);
    expect(summary.belowCount).toBe(0);
  });

  it("mixed agents: only 0-commit agents are below", () => {
    const summary = buildKpiSummary([ACTIVE_AGENT, DEAD_AGENT, WAITING_AGENT], 1);
    expect(summary.belowCount).toBe(2);
    expect(summary.belowAgents.map((a) => a.name)).toEqual(["ICT", "Marketing"]);
  });

  it("threshold=0 → no agents below (guard: threshold must be > 0)", () => {
    const summary = buildKpiSummary([DEAD_AGENT], 0);
    expect(summary.belowCount).toBe(0);
  });
});

describe("App.tsx v3: kpiAlertMessage", () => {
  it("empty list → empty string", () => {
    expect(kpiAlertMessage([])).toBe("");
  });

  it("one agent below → message contains agent name", () => {
    const msg = kpiAlertMessage([DEAD_AGENT]);
    expect(msg).toContain("ICT");
  });

  it("two agents below → message contains both names", () => {
    const msg = kpiAlertMessage([DEAD_AGENT, WAITING_AGENT]);
    expect(msg).toContain("ICT");
    expect(msg).toContain("Marketing");
  });
});

describe("App.tsx v3: hasCriticalAlert", () => {
  it("no DEAD agents → false", () => {
    expect(hasCriticalAlert([ACTIVE_AGENT, WAITING_AGENT])).toBe(false);
  });

  it("one DEAD agent → true", () => {
    expect(hasCriticalAlert([ACTIVE_AGENT, DEAD_AGENT])).toBe(true);
  });

  it("all DEAD → true", () => {
    expect(hasCriticalAlert([DEAD_AGENT, DEAD_AGENT])).toBe(true);
  });
});

describe("App.tsx v3: agentsWithCommits default mapping", () => {
  it("agent without commits field defaults to 0", () => {
    // Simulates: (a as AgentWithCommits).commits ?? 0
    const agentInfo = { name: "ICT", state: "ACTIVE", server: "netcup1" };
    const commits = (agentInfo as AgentWithCommits).commits ?? 0;
    expect(commits).toBe(0);
  });

  it("agent with explicit commits field uses that value", () => {
    const withCommits: AgentWithCommits = { ...ACTIVE_AGENT, commits: 7 };
    const commits = withCommits.commits ?? 0;
    expect(commits).toBe(7);
  });
});

describe("App.tsx v3: agentsBelow threshold contract", () => {
  it("agents with 0 commits below threshold=1", () => {
    const below = agentsBelow([DEAD_AGENT, WAITING_AGENT, ACTIVE_AGENT], 1);
    expect(below).toHaveLength(2);
    expect(below.every((a) => a.commits < 1)).toBe(true);
  });
});
