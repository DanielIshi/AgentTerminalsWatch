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

// 06.09.2026: zwei Fehler in einer Zeile.
// 1. process.env.REACT_APP_* ist Create-React-App-Konvention. Dieses Projekt
//    baut mit Vite, dort heisst es import.meta.env.VITE_*. Die Variable war
//    also nie gesetzt und der Fallback griff immer.
// 2. Der Fallback zeigte auf http://localhost:8000 -- im Browser des Nutzers
//    ist das DESSEN Rechner, nicht der Server. Gemessen: "Failed to fetch"
//    fuer /agents und /servers. Auf Port 8000 laeuft ausserdem eine
//    icon-search-api, also selbst lokal der falsche Dienst.
// Jetzt relativ: die App wird unter /atw/ ausgeliefert, die API liegt unter
// /atw-api/ auf demselben Host, hinter derselben Anmeldung.
const BASE_URL =
  (import.meta as any).env?.VITE_API_URL ?? "/atw-api";

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

export function killAgent(name: string): Promise<RestartResponse> {
  return _fetch<RestartResponse>(`/agents/${encodeURIComponent(name)}/kill`, {
    method: "POST",
  });
}

export function respawnAgent(name: string): Promise<RestartResponse> {
  return _fetch<RestartResponse>(`/agents/${encodeURIComponent(name)}/respawn`, {
    method: "POST",
  });
}
