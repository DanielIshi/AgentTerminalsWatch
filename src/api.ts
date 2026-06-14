/**
 * api.ts — fetch wrappers for AgentTerminalsWatch backend.
 *
 * fetchAgents(state?)  — GET /agents (optional state filter)
 * fetchAgent(name)     — GET /agents/{name}
 * fetchServers()       — GET /servers
 * restartAgent(name)   — POST /agents/{name}/restart
 */

export interface AgentInfo {
  name: string;
  server: string;
  state: "ACTIVE" | "WAITING" | "DEAD";
  technical_state: string;
  role: string;
  session: string | null;
}

export interface ServerInfo {
  name: string;
  host: string;
  ip: string;
}

export interface RestartResponse {
  name: string;
  queued: boolean;
  message: string;
}

const BASE_URL = process.env.REACT_APP_API_URL ?? "http://localhost:8000";

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export function fetchAgents(state?: "ACTIVE" | "WAITING" | "DEAD"): Promise<AgentInfo[]> {
  const qs = state ? `?state=${state}` : "";
  return _fetch<AgentInfo[]>(`/agents${qs}`);
}

export function fetchAgent(name: string): Promise<AgentInfo> {
  return _fetch<AgentInfo>(`/agents/${encodeURIComponent(name)}`);
}

export function fetchServers(): Promise<ServerInfo[]> {
  return _fetch<ServerInfo[]>("/servers");
}

export function restartAgent(name: string): Promise<RestartResponse> {
  return _fetch<RestartResponse>(`/agents/${encodeURIComponent(name)}/restart`, {
    method: "POST",
  });
}
