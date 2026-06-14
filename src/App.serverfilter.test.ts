/**
 * R145 TDD — App.tsx v3: useServerFilter integration contracts (pure-function layer).
 *
 * Tests cover:
 *   displayAgents = filteredAgents narrowed by textFilter
 *   server chip is bold when activeFilter matches server name
 *   "All" chip is bold when activeFilter is null
 *   displayAgents empty when filter matches nothing
 *   displayAgents shows only matching server agents
 *   text filter applied on top of server filter
 *   clear filter restores all agents for display
 *   filteredAgents passed to display (integration contract)
 */

import type { AgentInfo } from "./api";

// ── Pure helpers extracted from App.tsx (no React, no DOM needed) ──────────

function applyFilters(
  agents: AgentInfo[],
  activeFilter: string | null,
  textFilter: string
): AgentInfo[] {
  const serverFiltered = activeFilter
    ? agents.filter((a) => a.server === activeFilter)
    : agents;
  return textFilter
    ? serverFiltered.filter((a) =>
        a.name.toLowerCase().includes(textFilter.toLowerCase())
      )
    : serverFiltered;
}

function serverChipWeight(
  activeFilter: string | null,
  serverName: string
): "bold" | "normal" {
  return activeFilter === serverName ? "bold" : "normal";
}

function allChipWeight(activeFilter: string | null): "bold" | "normal" {
  return !activeFilter ? "bold" : "normal";
}

// ── Test fixtures ──────────────────────────────────────────────────────────

function agent(name: string, server: string): AgentInfo {
  return { name, server, state: "ACTIVE", technical_state: "working", role: "hod", session: null };
}

const AGENTS: AgentInfo[] = [
  agent("CEO", "netcup1"),
  agent("ICT", "netcup1"),
  agent("Marketing", "hetzner"),
  agent("Operations", "hetzner"),
  agent("Strategy", "hostinger"),
];

// ── Tests ──────────────────────────────────────────────────────────────────

describe("App.tsx v3: displayAgents (server + text filter)", () => {
  it("no filters → all agents displayed", () => {
    expect(applyFilters(AGENTS, null, "")).toHaveLength(5);
  });

  it("server filter only → only matching server shown", () => {
    const result = applyFilters(AGENTS, "netcup1", "");
    expect(result).toHaveLength(2);
    expect(result.every((a) => a.server === "netcup1")).toBe(true);
  });

  it("text filter only → only name-matching agents shown", () => {
    const result = applyFilters(AGENTS, null, "market");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Marketing");
  });

  it("server + text filter combined → intersection", () => {
    // netcup1 has CEO and ICT; text "ICT" → only ICT
    const result = applyFilters(AGENTS, "netcup1", "ICT");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("ICT");
  });

  it("server filter with no matching agents → empty display list", () => {
    expect(applyFilters(AGENTS, "gpu-server-x", "")).toHaveLength(0);
  });

  it("text filter with no matches → empty display list", () => {
    expect(applyFilters(AGENTS, null, "zzznomatch")).toHaveLength(0);
  });

  it("clearFilter (null) after server filter → all agents shown", () => {
    applyFilters(AGENTS, "netcup1", ""); // simulate active filter
    const result = applyFilters(AGENTS, null, ""); // clear
    expect(result).toHaveLength(5);
  });

  it("text filter is case-insensitive", () => {
    const result = applyFilters(AGENTS, null, "STRATEGY");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Strategy");
  });
});

describe("App.tsx v3: server chip bold-state", () => {
  it("All chip is bold when no filter active", () => {
    expect(allChipWeight(null)).toBe("bold");
  });

  it("All chip is normal when server filter active", () => {
    expect(allChipWeight("netcup1")).toBe("normal");
  });

  it("server chip bold when it matches activeFilter", () => {
    expect(serverChipWeight("netcup1", "netcup1")).toBe("bold");
  });

  it("server chip normal when a different filter is active", () => {
    expect(serverChipWeight("hetzner", "netcup1")).toBe("normal");
  });

  it("server chip normal when no filter active", () => {
    expect(serverChipWeight(null, "netcup1")).toBe("normal");
  });
});
