/**
 * R145 TDD — §356 Abs. 4/5 BGB WithdrawalWaiverCheckbox tests.
 *
 * Tests cover:
 *   T1: Checkbox renders with exact §356 legal text (LEGAL-final 2026-07-19)
 *   T2: data-testid="withdrawal-waiver-checkbox" present
 *   T3: default unchecked (aktive Zustimmung PFLICHT — kein Pre-Tick)
 *   T4: onChange handler fires on click
 *   T5: checked state changes on click
 *   T6: Widerrufsbelehrung link present
 *   T7: Muster-Widerrufsformular link present
 *   T8: onWaiverAccepted fires with ISO timestamp when checked
 *   T9: onWaiverAccepted fires with waiver_text_hash
 *   T10: waiver_text_hash is deterministic (same text → same hash)
 *   T11: WITHDRAWAL_WAIVER_TEXT matches exact LEGAL-approved wording
 *   T12: PaymentButton disabled when withdrawalWaiverAccepted=false
 *   T13: PaymentButton enabled when withdrawalWaiverAccepted=true
 *   T14: waiver-missing-hint visible when waiver not accepted
 */

// @vitest-environment jsdom
import React, { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { vi } from "vitest";

import {
  WithdrawalWaiverCheckbox,
  WITHDRAWAL_WAIVER_TEXT,
  WAIVER_VERSION,
  computeWaiverTextHash,
} from "../src/components/WithdrawalWaiverCheckbox";
import type { WaiverLogEntry } from "../src/components/WithdrawalWaiverCheckbox";
import { PaymentButton } from "../src/components/PaymentButton";

// ── T11: Exact legal text constant ──────────────────────────────────────────
describe("T11: WITHDRAWAL_WAIVER_TEXT exact LEGAL wording", () => {
  it("matches LEGAL-final 2026-07-19 §356 wording exactly", () => {
    expect(WITHDRAWAL_WAIVER_TEXT).toBe(
      "Ich verlange ausdrücklich, dass Sie mit der Ausführung der Dienstleistung " +
      "vor Ablauf der Widerrufsfrist beginnen. Mir ist bekannt, dass mein " +
      "Widerrufsrecht mit vollständiger Vertragserfüllung erlischt."
    );
  });

  it("contains mandatory §356 keyword 'ausdrücklich'", () => {
    expect(WITHDRAWAL_WAIVER_TEXT).toContain("ausdrücklich");
  });

  it("contains 'Widerrufsfrist'", () => {
    expect(WITHDRAWAL_WAIVER_TEXT).toContain("Widerrufsfrist");
  });

  it("contains 'erlischt' (Erlöschen des Widerrufsrechts)", () => {
    expect(WITHDRAWAL_WAIVER_TEXT).toContain("erlischt");
  });
});

// ── T1: Checkbox renders with correct text ────────────────────────────────
describe("T1: Renders with exact §356 legal text", () => {
  it("renders WITHDRAWAL_WAIVER_TEXT in the label", () => {
    render(
      <WithdrawalWaiverCheckbox checked={false} onChange={vi.fn()} />
    );
    expect(screen.getByText(WITHDRAWAL_WAIVER_TEXT, { exact: false })).toBeInTheDocument();
  });
});

// ── T2: data-testid ───────────────────────────────────────────────────────
describe("T2: data-testid present", () => {
  it('has data-testid="withdrawal-waiver-checkbox"', () => {
    render(
      <WithdrawalWaiverCheckbox checked={false} onChange={vi.fn()} />
    );
    expect(
      screen.getByTestId("withdrawal-waiver-checkbox")
    ).toBeInTheDocument();
  });
});

// ── T3: Default unchecked ─────────────────────────────────────────────────
describe("T3: Default unchecked (BGH Opt-in requirement)", () => {
  it("checkbox is unchecked by default when checked=false", () => {
    render(
      <WithdrawalWaiverCheckbox checked={false} onChange={vi.fn()} />
    );
    const checkbox = screen.getByTestId(
      "withdrawal-waiver-checkbox"
    ) as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
  });

  it("checkbox is checked when checked=true", () => {
    render(
      <WithdrawalWaiverCheckbox checked={true} onChange={vi.fn()} />
    );
    const checkbox = screen.getByTestId(
      "withdrawal-waiver-checkbox"
    ) as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });
});

// ── T4: onChange handler fires ────────────────────────────────────────────
describe("T4: onChange fires on click", () => {
  it("calls onChange when checkbox is clicked", () => {
    const onChange = vi.fn();
    render(<WithdrawalWaiverCheckbox checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("withdrawal-waiver-checkbox"));
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("onChange receives true when checking unchecked box", () => {
    const onChange = vi.fn();
    render(<WithdrawalWaiverCheckbox checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("withdrawal-waiver-checkbox"));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

// ── T5: Stateful wrapper verifies toggle behaviour ────────────────────────
describe("T5: Checkbox state changes on interaction", () => {
  function StatefulWrapper() {
    const [checked, setChecked] = useState(false);
    return (
      <WithdrawalWaiverCheckbox checked={checked} onChange={setChecked} />
    );
  }

  it("becomes checked after click", () => {
    render(<StatefulWrapper />);
    const cb = screen.getByTestId("withdrawal-waiver-checkbox") as HTMLInputElement;
    expect(cb.checked).toBe(false);
    fireEvent.click(cb);
    expect(cb.checked).toBe(true);
  });
});

// ── T6: Widerrufsbelehrung link ──────────────────────────────────────────
describe("T6: Widerrufsbelehrung link present", () => {
  it("renders a link to /legal/widerrufsbelehrung", () => {
    render(
      <WithdrawalWaiverCheckbox checked={false} onChange={vi.fn()} />
    );
    const link = screen.getByRole("link", { name: /Widerrufsbelehrung/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/legal/widerrufsbelehrung");
  });
});

// ── T7: Muster-Widerrufsformular link ───────────────────────────────────
describe("T7: Muster-Widerrufsformular link present", () => {
  it("renders a link to /legal/muster-widerrufsformular", () => {
    render(
      <WithdrawalWaiverCheckbox checked={false} onChange={vi.fn()} />
    );
    const link = screen.getByRole("link", { name: /Muster-Widerrufsformular/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/legal/muster-widerrufsformular");
  });
});

// ── T8: onWaiverAccepted fires with ISO timestamp ────────────────────────
describe("T8: onWaiverAccepted fires with ISO timestamp", () => {
  it("calls onWaiverAccepted with waiver_accepted_at ISO string when checked", () => {
    const onWaiverAccepted = vi.fn<[WaiverLogEntry], void>();
    render(
      <WithdrawalWaiverCheckbox
        checked={false}
        onChange={vi.fn()}
        onWaiverAccepted={onWaiverAccepted}
      />
    );
    fireEvent.click(screen.getByTestId("withdrawal-waiver-checkbox"));
    expect(onWaiverAccepted).toHaveBeenCalledTimes(1);
    const entry = onWaiverAccepted.mock.calls[0][0];
    // ISO 8601 format check
    expect(entry.waiver_accepted_at).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/
    );
  });

  it("does NOT call onWaiverAccepted when unchecking", () => {
    const onWaiverAccepted = vi.fn();
    render(
      <WithdrawalWaiverCheckbox
        checked={true}
        onChange={vi.fn()}
        onWaiverAccepted={onWaiverAccepted}
      />
    );
    fireEvent.click(screen.getByTestId("withdrawal-waiver-checkbox"));
    expect(onWaiverAccepted).not.toHaveBeenCalled();
  });
});

// ── T9: onWaiverAccepted fires with waiver_text_hash ────────────────────
describe("T9: onWaiverAccepted includes waiver_text_hash", () => {
  it("hash is a non-empty hex string", () => {
    const onWaiverAccepted = vi.fn<[WaiverLogEntry], void>();
    render(
      <WithdrawalWaiverCheckbox
        checked={false}
        onChange={vi.fn()}
        onWaiverAccepted={onWaiverAccepted}
      />
    );
    fireEvent.click(screen.getByTestId("withdrawal-waiver-checkbox"));
    const entry = onWaiverAccepted.mock.calls[0][0];
    expect(entry.waiver_text_hash).toMatch(/^[0-9a-f]+$/i);
    expect(entry.waiver_text_hash.length).toBeGreaterThan(0);
  });
});

// ── T10: waiver_text_hash is deterministic ───────────────────────────────
describe("T10: computeWaiverTextHash is deterministic", () => {
  it("same text → same hash", () => {
    const h1 = computeWaiverTextHash(WITHDRAWAL_WAIVER_TEXT);
    const h2 = computeWaiverTextHash(WITHDRAWAL_WAIVER_TEXT);
    expect(h1).toBe(h2);
  });

  it("different text → different hash", () => {
    const h1 = computeWaiverTextHash(WITHDRAWAL_WAIVER_TEXT);
    const h2 = computeWaiverTextHash("Ich stimme zu.");
    expect(h1).not.toBe(h2);
  });
});

// ── T12: PaymentButton disabled when waiver not accepted ─────────────────
describe("T12: PaymentButton disabled when withdrawalWaiverAccepted=false", () => {
  it("button is disabled", () => {
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        onCheckout={vi.fn()}
        withdrawalWaiverAccepted={false}
      />
    );
    expect(screen.getByTestId("payment-button-solo-monthly")).toBeDisabled();
  });

  it("shows waiver-missing-hint when waiver not accepted but checkout provided", () => {
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        onCheckout={vi.fn()}
        withdrawalWaiverAccepted={false}
      />
    );
    expect(screen.getByTestId("waiver-missing-hint")).toBeInTheDocument();
  });
});

// ── T13: PaymentButton enabled when waiver accepted ──────────────────────
describe("T13: PaymentButton enabled when withdrawalWaiverAccepted=true", () => {
  it("button is NOT disabled", () => {
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        onCheckout={vi.fn()}
        withdrawalWaiverAccepted={true}
      />
    );
    expect(screen.getByTestId("payment-button-solo-monthly")).not.toBeDisabled();
  });

  it("waiver-missing-hint NOT shown when waiver accepted", () => {
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        onCheckout={vi.fn()}
        withdrawalWaiverAccepted={true}
      />
    );
    expect(
      screen.queryByTestId("waiver-missing-hint")
    ).not.toBeInTheDocument();
  });
});

// ── T14: waiver-missing-hint visibility ──────────────────────────────────
describe("T14: waiver-missing-hint visibility", () => {
  it("NOT shown when onCheckout is undefined (no checkout flow active)", () => {
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        withdrawalWaiverAccepted={false}
      />
    );
    expect(
      screen.queryByTestId("waiver-missing-hint")
    ).not.toBeInTheDocument();
  });
});

// ── T16: waiver_version field in WaiverLogEntry ──────────────────────────────
describe("T16: waiver_version field in WaiverLogEntry (LEGAL Kriterium #5)", () => {
  it("onWaiverAccepted includes waiver_version field", () => {
    const onWaiverAccepted = vi.fn<[WaiverLogEntry], void>();
    render(
      <WithdrawalWaiverCheckbox
        checked={false}
        onChange={vi.fn()}
        onWaiverAccepted={onWaiverAccepted}
      />
    );
    fireEvent.click(screen.getByTestId("withdrawal-waiver-checkbox"));
    const entry = onWaiverAccepted.mock.calls[0][0];
    expect(entry.waiver_version).toBeDefined();
    expect(entry.waiver_version).toBe(WAIVER_VERSION);
  });

  it("waiver_version matches format waiver_vN_YYYY-MM-DD", () => {
    expect(WAIVER_VERSION).toMatch(/^waiver_v\d+_\d{4}-\d{2}-\d{2}$/);
  });

  it("waiver_version is 'waiver_v1_2026-07-19' (current LEGAL-approved version)", () => {
    expect(WAIVER_VERSION).toBe("waiver_v1_2026-07-19");
  });
});

// ── T17: WAIVER_VERSION constant present and exported ────────────────────────
describe("T17: WAIVER_VERSION constant exported", () => {
  it("WAIVER_VERSION is a non-empty string", () => {
    expect(typeof WAIVER_VERSION).toBe("string");
    expect(WAIVER_VERSION.length).toBeGreaterThan(0);
  });

  it("WAIVER_VERSION starts with 'waiver_v'", () => {
    expect(WAIVER_VERSION).toMatch(/^waiver_v/);
  });
});
