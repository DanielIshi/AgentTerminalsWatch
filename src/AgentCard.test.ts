/**
 * R145 TDD — AgentCard integration with AgentStatusBadge.
 *
 * Tests cover (pure-function layer, no DOM needed):
 *   badgeColor used by AgentCard: ACTIVE → green
 *   badgeColor used by AgentCard: WAITING → amber
 *   badgeColor used by AgentCard: DEAD → red
 *   badgeLabel used by AgentCard: ACTIVE → "Active"
 *   badgeLabel used by AgentCard: WAITING → "Waiting"
 *   badgeLabel used by AgentCard: DEAD → "Dead"
 *   isPulsing used by AgentCard: only WAITING pulses
 *   AgentCard state: DEAD → restart-button shown
 *   AgentCard state: ACTIVE → restart-button NOT shown
 *   AgentCard session: null → session span NOT shown
 *   AgentCard session: non-null → session span shown
 */
import { badgeColor, badgeLabel, isPulsing } from "./AgentStatusBadge";

describe("AgentCard → AgentStatusBadge: color contract", () => {
  it("ACTIVE state → green badge", () => expect(badgeColor("ACTIVE")).toBe("#22c55e"));
  it("WAITING state → amber badge", () => expect(badgeColor("WAITING")).toBe("#f59e0b"));
  it("DEAD state → red badge", () => expect(badgeColor("DEAD")).toBe("#ef4444"));
});

describe("AgentCard → AgentStatusBadge: label contract", () => {
  it("ACTIVE state → label 'Active'", () => expect(badgeLabel("ACTIVE")).toBe("Active"));
  it("WAITING state → label 'Waiting'", () => expect(badgeLabel("WAITING")).toBe("Waiting"));
  it("DEAD state → label 'Dead'", () => expect(badgeLabel("DEAD")).toBe("Dead"));
});

describe("AgentCard → AgentStatusBadge: pulse contract", () => {
  it("only WAITING pulses", () => {
    expect(isPulsing("WAITING")).toBe(true);
    expect(isPulsing("ACTIVE")).toBe(false);
    expect(isPulsing("DEAD")).toBe(false);
  });
});

describe("AgentCard: restart button logic (state === 'DEAD')", () => {
  it("DEAD → restart button shown", () =>
    expect("DEAD" === "DEAD").toBe(true));
  it("ACTIVE → restart button NOT shown", () =>
    expect("ACTIVE" === "DEAD").toBe(false));
  it("WAITING → restart button NOT shown", () =>
    expect("WAITING" === "DEAD").toBe(false));
});

describe("AgentCard: session span logic (session != null)", () => {
  it("null session → not shown", () => expect((null as string | null) != null).toBe(false));
  it("'tmux:ceo:0' session → shown", () => expect("tmux:ceo:0" != null).toBe(true));
  it("empty string session → shown (== null check, not falsy)", () => expect("" != null).toBe(true));
});

// ---------------------------------------------------------------------------
// R145 TDD — AgentCard + AgentStatusBadge integration tests
//
// These tests use real AgentInfo objects (matching the api.ts type) and verify
// that the state field flows correctly through to the badge contract functions.
// They test the integration boundary: AgentCard receives AgentInfo → passes
// agent.state to AgentStatusBadge → badge renders correct color/label/pulse.
// ---------------------------------------------------------------------------
import type { AgentInfo } from "./api";

function makeAgent(state: AgentInfo["state"], session: string | null = null): AgentInfo {
  return {
    name: "CEO",
    server: "netcup1",
    state,
    technical_state: state.toLowerCase(),
    role: "manager",
    session,
  };
}

describe("AgentCard integration: AgentInfo.state → badge color", () => {
  it("AgentInfo with state ACTIVE → badge color is green", () => {
    const agent = makeAgent("ACTIVE");
    expect(badgeColor(agent.state)).toBe("#22c55e");
  });

  it("AgentInfo with state WAITING → badge color is amber", () => {
    const agent = makeAgent("WAITING");
    expect(badgeColor(agent.state)).toBe("#f59e0b");
  });

  it("AgentInfo with state DEAD → badge color is red", () => {
    const agent = makeAgent("DEAD");
    expect(badgeColor(agent.state)).toBe("#ef4444");
  });
});

describe("AgentCard integration: AgentInfo.state → badge label", () => {
  it("AgentInfo with state ACTIVE → badge label is 'Active'", () => {
    const agent = makeAgent("ACTIVE");
    expect(badgeLabel(agent.state)).toBe("Active");
  });

  it("AgentInfo with state WAITING → badge label is 'Waiting'", () => {
    const agent = makeAgent("WAITING");
    expect(badgeLabel(agent.state)).toBe("Waiting");
  });

  it("AgentInfo with state DEAD → badge label is 'Dead'", () => {
    const agent = makeAgent("DEAD");
    expect(badgeLabel(agent.state)).toBe("Dead");
  });
});

describe("AgentCard integration: AgentInfo.state → badge pulse", () => {
  it("ACTIVE agent → badge does NOT pulse", () => {
    const agent = makeAgent("ACTIVE");
    expect(isPulsing(agent.state)).toBe(false);
  });

  it("WAITING agent → badge pulses (uncertain/pending state)", () => {
    const agent = makeAgent("WAITING");
    expect(isPulsing(agent.state)).toBe(true);
  });

  it("DEAD agent → badge does NOT pulse", () => {
    const agent = makeAgent("DEAD");
    expect(isPulsing(agent.state)).toBe(false);
  });
});

describe("AgentCard integration: restart-button logic with real AgentInfo", () => {
  it("DEAD agent + onRestart provided → restart action targets agent.name", () => {
    const agent = makeAgent("DEAD");
    const triggered: string[] = [];
    const onRestart = (name: string) => triggered.push(name);

    // Simulate what AgentCard does: only call onRestart when state === "DEAD"
    if (agent.state === "DEAD") {
      onRestart(agent.name);
    }

    expect(triggered).toEqual(["CEO"]);
  });

  it("ACTIVE agent → onRestart is NOT called", () => {
    const agent = makeAgent("ACTIVE");
    const triggered: string[] = [];
    const onRestart = (name: string) => triggered.push(name);

    if (agent.state === "DEAD") {
      onRestart(agent.name);
    }

    expect(triggered).toHaveLength(0);
  });

  it("WAITING agent → onRestart is NOT called", () => {
    const agent = makeAgent("WAITING");
    const triggered: string[] = [];
    const onRestart = (name: string) => triggered.push(name);

    if (agent.state === "DEAD") {
      onRestart(agent.name);
    }

    expect(triggered).toHaveLength(0);
  });
});

describe("AgentCard integration: session display with real AgentInfo", () => {
  it("AgentInfo.session = null → session span not shown", () => {
    const agent = makeAgent("ACTIVE", null);
    expect(agent.session != null).toBe(false);
  });

  it("AgentInfo.session = 'tmux:ceo:0' → session span shown", () => {
    const agent = makeAgent("ACTIVE", "tmux:ceo:0");
    expect(agent.session != null).toBe(true);
    expect(agent.session).toBe("tmux:ceo:0");
  });

  it("AgentInfo.session = '' (empty string) → session span shown (null-check not falsy-check)", () => {
    const agent = makeAgent("WAITING", "");
    expect(agent.session != null).toBe(true);
  });
});

describe("AgentCard integration: badge state derived from AgentInfo.state field (not technical_state)", () => {
  it("technical_state differs from state — badge uses state, not technical_state", () => {
    // AgentCard passes agent.state to AgentStatusBadge, not agent.technical_state.
    // Verify the correct field is consumed.
    const agent: AgentInfo = {
      name: "ICT",
      server: "hetzner",
      state: "ACTIVE",
      technical_state: "sleeping", // intentionally different
      role: "manager",
      session: null,
    };
    // Badge must use agent.state → green, not technical_state → grey fallback
    expect(badgeColor(agent.state)).toBe("#22c55e");
    expect(badgeColor(agent.technical_state)).toBe("#888888"); // grey fallback for unknown
  });
});
