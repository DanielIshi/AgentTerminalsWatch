/**
 * R145 TDD — AgentStatusBadge tests.
 *
 * Tests cover:
 *   badgeColor: ACTIVE → green
 *   badgeColor: WAITING → amber
 *   badgeColor: DEAD → red
 *   badgeColor: unknown state → grey fallback
 *   badgeColor: empty string → grey fallback
 *   badgeColor: lowercase "active" → grey fallback (case-sensitive)
 *   badgeColor: whitespace-prefixed " ACTIVE" → grey fallback
 *   badgeLabel: ACTIVE → "Active"
 *   badgeLabel: WAITING → "Waiting"
 *   badgeLabel: DEAD → "Dead"
 *   badgeLabel: unknown → returns state as-is
 *   badgeLabel: empty string → returns ""
 *   badgeLabel: lowercase "active" → returns "active" as-is (case-sensitive)
 *   isPulsing: ACTIVE → false
 *   isPulsing: WAITING → true
 *   isPulsing: DEAD → false
 *   isPulsing: unknown → false
 *   isPulsing: empty string → false
 *   isPulsing: lowercase "waiting" → false (case-sensitive)
 *   component style derivation: WAITING → opacity 0.8, animation defined
 *   component style derivation: ACTIVE → opacity 1, no animation
 *   component style derivation: DEAD → opacity 1, no animation
 *   component style derivation: unknown → opacity 1, no animation
 */
import { badgeColor, badgeLabel, isPulsing } from "./AgentStatusBadge";

describe("badgeColor", () => {
  it("ACTIVE → green", () => expect(badgeColor("ACTIVE")).toBe("#22c55e"));
  it("WAITING → amber", () => expect(badgeColor("WAITING")).toBe("#f59e0b"));
  it("DEAD → red", () => expect(badgeColor("DEAD")).toBe("#ef4444"));
  it("unknown → grey fallback", () => expect(badgeColor("OTHER")).toBe("#888888"));
  it("empty string → grey fallback", () => expect(badgeColor("")).toBe("#888888"));
  it("lowercase 'active' → grey fallback (case-sensitive match)", () =>
    expect(badgeColor("active")).toBe("#888888"));
  it("whitespace-prefixed ' ACTIVE' → grey fallback (exact match only)", () =>
    expect(badgeColor(" ACTIVE")).toBe("#888888"));
});

describe("badgeLabel", () => {
  it("ACTIVE → Active", () => expect(badgeLabel("ACTIVE")).toBe("Active"));
  it("WAITING → Waiting", () => expect(badgeLabel("WAITING")).toBe("Waiting"));
  it("DEAD → Dead", () => expect(badgeLabel("DEAD")).toBe("Dead"));
  it("unknown → returns state as-is", () => expect(badgeLabel("STUCK")).toBe("STUCK"));
  it("empty string → returns empty string as-is", () => expect(badgeLabel("")).toBe(""));
  it("lowercase 'active' → returns 'active' as-is (case-sensitive)", () =>
    expect(badgeLabel("active")).toBe("active"));
});

describe("isPulsing", () => {
  it("ACTIVE → false", () => expect(isPulsing("ACTIVE")).toBe(false));
  it("WAITING → true (indicates pending/uncertain state)", () => expect(isPulsing("WAITING")).toBe(true));
  it("DEAD → false", () => expect(isPulsing("DEAD")).toBe(false));
  it("unknown → false", () => expect(isPulsing("OTHER")).toBe(false));
  it("empty string → false", () => expect(isPulsing("")).toBe(false));
  it("lowercase 'waiting' → false (case-sensitive, only 'WAITING' pulses)", () =>
    expect(isPulsing("waiting")).toBe(false));
});

describe("component style derivation (via pure functions)", () => {
  // Verifies the logic the component uses to derive style props:
  //   opacity: isPulsing(state) ? 0.8 : 1
  //   animation: isPulsing(state) ? "pulse 1.5s infinite" : undefined

  it.each([
    ["ACTIVE", 1, undefined],
    ["DEAD", 1, undefined],
    ["OTHER", 1, undefined],
    ["", 1, undefined],
    ["WAITING", 0.8, "pulse 1.5s infinite"],
  ] as const)(
    "state=%s → opacity=%s, animation=%s",
    (state, expectedOpacity, expectedAnimation) => {
      const pulse = isPulsing(state);
      const opacity = pulse ? 0.8 : 1;
      const animation = pulse ? "pulse 1.5s infinite" : undefined;
      expect(opacity).toBe(expectedOpacity);
      expect(animation).toBe(expectedAnimation);
    }
  );
});
