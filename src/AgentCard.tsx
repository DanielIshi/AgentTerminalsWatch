import React from "react";
import type { AgentInfo } from "./api";
import { AgentStatusBadge } from "./AgentStatusBadge";

interface AgentCardProps {
  agent: AgentInfo;
  onRestart?: (name: string) => void;
}

export function AgentCard({ agent, onRestart }: AgentCardProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
        padding: "8px 0",
        borderBottom: "1px solid #333",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <AgentStatusBadge state={agent.state} />
        <span style={{ flex: 1 }}>{agent.name}</span>
        <span style={{ color: "#888", fontSize: 12 }}>{agent.server}</span>
        {agent.state === "DEAD" && onRestart && (
          <button onClick={() => onRestart(agent.name)} style={{ fontSize: 11, padding: "2px 6px" }}>
            Restart
          </button>
        )}
      </div>
      {agent.session != null && (
        <span style={{ color: "#06b6d4", fontSize: 11, paddingLeft: 78 }}>
          {agent.session}
        </span>
      )}
    </div>
  );
}
