import React from "react";

const COLORS: Record<string, string> = {
  ACTIVE: "#22c55e",
  WAITING: "#f59e0b",
  DEAD: "#ef4444",
};

const LABELS: Record<string, string> = {
  ACTIVE: "Active",
  WAITING: "Waiting",
  DEAD: "Dead",
};

export function badgeColor(state: string): string {
  return COLORS[state] ?? "#888888";
}

export function badgeLabel(state: string): string {
  return LABELS[state] ?? state;
}

export function isPulsing(state: string): boolean {
  return state === "WAITING";
}

interface AgentStatusBadgeProps {
  state: string;
}

export function AgentStatusBadge({ state }: AgentStatusBadgeProps) {
  const color = badgeColor(state);
  const label = badgeLabel(state);
  const pulse = isPulsing(state);

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        backgroundColor: color,
        color: "#000",
        fontWeight: "bold",
        fontSize: 11,
        opacity: pulse ? 0.8 : 1,
        animation: pulse ? "pulse 1.5s infinite" : undefined,
      }}
    >
      {label}
    </span>
  );
}
