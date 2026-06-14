/**
 * App.tsx v3 — AgentTerminalsWatch main component.
 *
 * Integrates useDeadAgentAlert + useServerFilter + AgentStatusBadge + useKpiAlert.
 * Shows: KPI alert bar, server-filter chips, text search, agent list.
 */
import React, { useEffect, useState } from "react";
import type { AgentInfo, ServerInfo } from "./api";
import { fetchAgents, fetchServers, restartAgent } from "./api";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { useDeadAgentAlert } from "./useDeadAgentAlert";
import { useKpiAlert, buildKpiSummary } from "./useKpiAlert";
import type { AgentWithCommits } from "./useKpiAlert";
import { useServerFilter } from "./useServerFilter";

function AgentRow({ agent, onRestart }: { agent: AgentInfo; onRestart: (name: string) => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: "1px solid #333" }}>
      <AgentStatusBadge state={agent.state} />
      <span style={{ flex: 1 }}>{agent.name}</span>
      <span style={{ color: "#888", fontSize: 12 }}>{agent.server}</span>
      {agent.state === "DEAD" && (
        <button onClick={() => onRestart(agent.name)} style={{ fontSize: 11, padding: "2px 6px" }}>
          Restart
        </button>
      )}
    </div>
  );
}

export default function App() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [servers, setServers] = useState<ServerInfo[]>([]);
  const [textFilter, setTextFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { deadCount, enabled: alertEnabled, setEnabled: setAlertEnabled } = useDeadAgentAlert(agents);
  const { activeFilter, filteredAgents, filterByServer, clearFilter } = useServerFilter(agents);

  // Treat all agents as having 0 commits unless API provides commit data
  const agentsWithCommits: AgentWithCommits[] = agents.map((a) => ({
    ...a,
    commits: (a as AgentWithCommits).commits ?? 0,
  }));
  const kpiSummary = buildKpiSummary(agentsWithCommits, 1);
  const { alertFired } = useKpiAlert(agentsWithCommits, { commitThreshold: 1 });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [a, s] = await Promise.all([fetchAgents(), fetchServers()]);
        if (!cancelled) {
          setAgents(a);
          setServers(s);
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(String(e));
          setLoading(false);
        }
      }
    }
    load();
    const interval = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const handleRestart = async (name: string) => {
    try {
      await restartAgent(name);
      alert(`Restart queued for ${name}`);
    } catch {
      alert(`Restart failed for ${name}`);
    }
  };

  const displayAgents = filteredAgents.filter((a) =>
    textFilter ? a.name.toLowerCase().includes(textFilter.toLowerCase()) : true
  );

  if (loading) return <div style={{ padding: 24 }}>Loading agents…</div>;
  if (error) return <div style={{ padding: 24, color: "#ef4444" }}>Error: {error}</div>;

  return (
    <div style={{ fontFamily: "monospace", padding: 16, maxWidth: 600 }}>
      <h2 style={{ margin: "0 0 8px" }}>AgentTerminalsWatch</h2>

      {/* KPI alert bar */}
      {alertFired && kpiSummary.belowCount > 0 && (
        <div style={{ background: "#7f1d1d", color: "#fca5a5", padding: "6px 10px", borderRadius: 4, marginBottom: 8, fontSize: 12 }}>
          ⚠ KPI below threshold: {kpiSummary.belowAgents.map((a) => a.name).join(", ")}
        </div>
      )}

      {/* Dead alert bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ color: deadCount > 0 ? "#ef4444" : "#22c55e" }}>
          {deadCount} DEAD
        </span>
        <label style={{ fontSize: 12, color: "#888" }}>
          <input
            type="checkbox"
            checked={alertEnabled}
            onChange={(e) => setAlertEnabled(e.target.checked)}
            style={{ marginRight: 4 }}
          />
          Alerts
        </label>
      </div>

      {/* Server filter chips */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
        <button
          onClick={clearFilter}
          style={{ fontWeight: !activeFilter ? "bold" : "normal", fontSize: 12 }}
        >
          All
        </button>
        {servers.map((s) => (
          <button
            key={s.name}
            onClick={() => filterByServer(s.name)}
            style={{ fontWeight: activeFilter === s.name ? "bold" : "normal", fontSize: 12 }}
          >
            {s.name}
          </button>
        ))}
      </div>

      {/* Text search */}
      <input
        type="text"
        placeholder="Filter agents…"
        value={textFilter}
        onChange={(e) => setTextFilter(e.target.value)}
        style={{ width: "100%", marginBottom: 8, padding: 4, boxSizing: "border-box" }}
      />

      {/* Agent list */}
      {displayAgents.map((a) => (
        <AgentRow key={a.name} agent={a} onRestart={handleRestart} />
      ))}

      {displayAgents.length === 0 && (
        <div style={{ color: "#888", padding: "8px 0" }}>No agents match filter.</div>
      )}
    </div>
  );
}
