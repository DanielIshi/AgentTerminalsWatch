import { useState, useEffect, useRef } from "react";
import type { AgentInfo } from "./api";

export interface AgentWithCommits extends AgentInfo {
  commits: number;
}

export interface KpiSummary {
  total: number;
  belowCount: number;
  belowAgents: AgentWithCommits[];
}

// ── Pure helpers (exported for unit testing) ──────────────────────────────────

export function agentsBelow(agents: AgentWithCommits[], threshold: number): AgentWithCommits[] {
  if (threshold <= 0) return [];
  return agents.filter((a) => a.commits < threshold);
}

export function kpiAlertMessage(below: AgentWithCommits[]): string {
  if (below.length === 0) return "";
  const names = below.map((a) => a.name).join(", ");
  return `KPI below threshold: ${names}`;
}

export function hasCriticalAlert(agents: AgentWithCommits[]): boolean {
  return agents.some((a) => a.state === "DEAD");
}

export function buildKpiSummary(agents: AgentWithCommits[], threshold: number): KpiSummary {
  const below = agentsBelow(agents, threshold);
  return {
    total: agents.length,
    belowCount: below.length,
    belowAgents: below,
  };
}

// ── Alert-fire decision (pure, testable — extracted from hook) ────────────────

export interface ShouldFireAlertParams {
  prevBelow: number;
  currentBelow: number;
  critical: boolean;
}

/** Returns true when a new alert condition has emerged. Pure — no side effects. */
export function shouldFireAlert({ prevBelow, currentBelow, critical }: ShouldFireAlertParams): boolean {
  if (currentBelow === 0) return false;
  return currentBelow > prevBelow || critical;
}

// ── React hook ────────────────────────────────────────────────────────────────

export interface UseKpiAlertOptions {
  commitThreshold?: number;
  enabled?: boolean;
}

export function useKpiAlert(
  agents: AgentWithCommits[],
  { commitThreshold = 1, enabled = true }: UseKpiAlertOptions = {}
) {
  const [alertFired, setAlertFired] = useState(false);
  const prevBelowCount = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const summary = buildKpiSummary(agents, commitThreshold);
    const critical = hasCriticalAlert(agents);

    if (shouldFireAlert({ prevBelow: prevBelowCount.current, currentBelow: summary.belowCount, critical })) {
      // alertFired drives the UI bar — always set, independent of Notification permission
      setAlertFired(true);
      // Browser notification is optional side-effect only
      const msg = kpiAlertMessage(summary.belowAgents);
      if (msg && typeof Notification !== "undefined" && Notification.permission === "granted") {
        new Notification("KPI Alert", { body: msg, tag: "kpi-alert" });
      }
    }
    prevBelowCount.current = summary.belowCount;
  }, [agents, commitThreshold, enabled]);

  return {
    summary: buildKpiSummary(agents, commitThreshold),
    critical: hasCriticalAlert(agents),
    alertFired,
  };
}
