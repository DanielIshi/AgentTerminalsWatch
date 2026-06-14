/**
 * @vitest-environment jsdom
 *
 * R145 TDD — useKpiAlert React hook integration tests.
 *
 * Tests cover the hook's return shape and state transitions:
 *   - summary (total, belowCount, belowAgents) reflects current agents
 *   - critical reflects DEAD agent presence
 *   - alertFired starts false when nobody below threshold
 *   - alertFired becomes true when agents drop below threshold on re-render
 *   - alertFired stays false when enabled=false
 *   - default commitThreshold=1 is respected
 */

import { renderHook, act } from "@testing-library/react";
import { useKpiAlert } from "./useKpiAlert";
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

function makeAgents(overrides: Array<Partial<AgentInfo> & { commits?: number }> = []) {
  return overrides.map((o) => agent(o));
}

describe("useKpiAlert hook", () => {
  it("returns summary with correct total and belowCount", () => {
    const agents = makeAgents([{ commits: 2 }, { commits: 10 }]);
    const { result } = renderHook(() => useKpiAlert(agents, { commitThreshold: 5 }));
    expect(result.current.summary.total).toBe(2);
    expect(result.current.summary.belowCount).toBe(1);
  });

  it("returns critical=false when all ACTIVE", () => {
    const agents = makeAgents([{ state: "ACTIVE", commits: 10 }]);
    const { result } = renderHook(() => useKpiAlert(agents));
    expect(result.current.critical).toBe(false);
  });

  it("returns critical=true when any agent is DEAD", () => {
    const agents = makeAgents([{ state: "DEAD", commits: 0 }, { state: "ACTIVE", commits: 5 }]);
    const { result } = renderHook(() => useKpiAlert(agents));
    expect(result.current.critical).toBe(true);
  });

  it("alertFired is false initially when no agents below threshold", () => {
    const agents = makeAgents([{ commits: 10 }, { commits: 20 }]);
    const { result } = renderHook(() => useKpiAlert(agents, { commitThreshold: 5 }));
    expect(result.current.alertFired).toBe(false);
  });

  it("alertFired becomes true when agents drop below threshold on re-render", () => {
    // Start with nobody below
    let currentAgents = makeAgents([{ commits: 10 }]);
    const { result, rerender } = renderHook(() => useKpiAlert(currentAgents, { commitThreshold: 5 }));

    expect(result.current.alertFired).toBe(false);

    // Now agents drop below threshold
    act(() => {
      currentAgents = makeAgents([{ commits: 1 }]);
    });
    rerender();

    expect(result.current.alertFired).toBe(true);
  });

  it("alertFired stays false when enabled=false", () => {
    let currentAgents = makeAgents([{ commits: 10 }]);
    const { result, rerender } = renderHook(() =>
      useKpiAlert(currentAgents, { commitThreshold: 5, enabled: false })
    );

    act(() => {
      currentAgents = makeAgents([{ commits: 1 }]);
    });
    rerender();

    expect(result.current.alertFired).toBe(false);
  });

  it("summary.belowAgents contains agents below threshold", () => {
    const agents = makeAgents([{ name: "low-agent", commits: 0 }, { name: "high-agent", commits: 10 }]);
    const { result } = renderHook(() => useKpiAlert(agents, { commitThreshold: 5 }));
    expect(result.current.summary.belowAgents.map((a) => a.name)).toContain("low-agent");
    expect(result.current.summary.belowAgents.map((a) => a.name)).not.toContain("high-agent");
  });

  it("respects default commitThreshold=1", () => {
    const agents = makeAgents([{ commits: 0 }, { commits: 5 }]);
    const { result } = renderHook(() => useKpiAlert(agents));
    // commits=0 is below default threshold=1
    expect(result.current.summary.belowCount).toBe(1);
  });
});
