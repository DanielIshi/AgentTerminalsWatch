/**
 * useServerFilter — React hook for server-scoped agent filtering.
 *
 * filterByServer(server) — activate filter for a specific server
 * clearFilter()          — show all servers
 * activeFilter           — current server name or null
 * filteredAgents         — agents matching current filter
 */
import { useCallback, useState } from "react";
import type { AgentInfo } from "./api";

export interface UseServerFilterResult {
  activeFilter: string | null;
  filteredAgents: AgentInfo[];
  filterByServer: (server: string) => void;
  clearFilter: () => void;
}

export function useServerFilter(agents: AgentInfo[]): UseServerFilterResult {
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const filterByServer = useCallback((server: string) => {
    setActiveFilter(server);
  }, []);

  const clearFilter = useCallback(() => {
    setActiveFilter(null);
  }, []);

  const filteredAgents = activeFilter
    ? agents.filter((a) => a.server === activeFilter)
    : agents;

  return { activeFilter, filteredAgents, filterByServer, clearFilter };
}
