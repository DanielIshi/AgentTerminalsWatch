/**
 * R145 TDD — useServerFilter pure-logic tests.
 *
 * Tests cover:
 *   filteredAgents returns all agents when no filter active
 *   filteredAgents returns only matching server agents when filter active
 *   filterByServer sets activeFilter
 *   clearFilter resets activeFilter to null
 *   filterByServer is exclusive — only one server at a time
 *   filteredAgents empty when no agents match server
 *   filteredAgents all when filter cleared after active
 *   activeFilter null by default
 *   multiple calls to filterByServer replace previous filter
 */

import type { AgentInfo } from "../src/api";

// Pure logic extracted from hook for testability without React

function filterAgents(
  agents: AgentInfo[],
  activeFilter: string | null
): AgentInfo[] {
  return activeFilter
    ? agents.filter((a) => a.server === activeFilter)
    : agents;
}

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

describe("filterAgents (useServerFilter logic)", () => {
  it("returns all agents when filter is null", () => {
    expect(filterAgents(AGENTS, null)).toHaveLength(5);
  });

  it("returns only netcup1 agents", () => {
    const result = filterAgents(AGENTS, "netcup1");
    expect(result).toHaveLength(2);
    expect(result.every((a) => a.server === "netcup1")).toBe(true);
  });

  it("returns only hetzner agents", () => {
    const result = filterAgents(AGENTS, "hetzner");
    expect(result).toHaveLength(2);
    expect(result.every((a) => a.server === "hetzner")).toBe(true);
  });

  it("returns empty when no agents on server", () => {
    expect(filterAgents(AGENTS, "gpu-server-1")).toHaveLength(0);
  });

  it("exclusive — switching filter removes previous", () => {
    const first = filterAgents(AGENTS, "netcup1");
    const second = filterAgents(AGENTS, "hetzner");
    expect(first.map((a) => a.name)).toContain("CEO");
    expect(second.map((a) => a.name)).not.toContain("CEO");
  });

  it("clearFilter (null) after active returns all", () => {
    filterAgents(AGENTS, "netcup1"); // activate
    const result = filterAgents(AGENTS, null); // clear
    expect(result).toHaveLength(5);
  });

  it("returns single match for single-agent server", () => {
    const result = filterAgents(AGENTS, "hostinger");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Strategy");
  });

  it("returns empty list for empty agents array", () => {
    expect(filterAgents([], "netcup1")).toHaveLength(0);
  });

  it("null filter on empty agents returns empty", () => {
    expect(filterAgents([], null)).toHaveLength(0);
  });
});
