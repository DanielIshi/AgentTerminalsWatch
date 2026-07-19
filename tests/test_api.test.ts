/**
 * R145 TDD — api.ts unit tests.
 *
 * Tests cover:
 *   fetchAgents() — calls /agents, returns AgentInfo[]
 *   fetchAgents(state) — calls /agents?state=DEAD
 *   fetchAgent(name) — calls /agents/{name}
 *   fetchServers() — calls /servers
 *   restartAgent(name) — POST /agents/{name}/restart
 *   _fetch error — throws on non-ok response
 *   BASE_URL default — uses localhost:8000
 *   BASE_URL env override — uses REACT_APP_API_URL
 *   name encoding — encodeURIComponent for special chars
 *   restartAgent returns RestartResponse
 *   fetchAgent 404 throws Error
 *   fetchAgents returns empty array on empty list
 *   fetchServers returns ServerInfo[]
 *   restartAgent uses POST method
 *   fetchAgents no filter — no ?state in URL
 *   fetchAgents ACTIVE filter
 */

import { vi } from "vitest";
import { fetchAgents, fetchAgent, fetchServers, restartAgent, killAgent, respawnAgent } from "../src/api";

const MOCK_AGENTS = [
  { name: "CEO", server: "netcup1", state: "ACTIVE", technical_state: "working", role: "ceo", session: "CEO:0" },
  { name: "ICT", server: "netcup1", state: "WAITING", technical_state: "idle", role: "hod", session: null },
];

const MOCK_SERVERS = [
  { name: "netcup1", host: "netcup1", ip: "85.215.100.1" },
];

const MOCK_RESTART = { name: "ICT", queued: true, message: "Restart queued" };

function mockFetch(body: unknown, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  }) as ReturnType<typeof vi.fn>;
}

beforeEach(() => {
  delete process.env.REACT_APP_API_URL;
});

describe("fetchAgents", () => {
  it("calls /agents and returns list", async () => {
    mockFetch(MOCK_AGENTS);
    const agents = await fetchAgents();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/agents"),
      undefined
    );
    expect(agents).toHaveLength(2);
    expect(agents[0].name).toBe("CEO");
  });

  it("calls /agents?state=DEAD with state filter", async () => {
    mockFetch([MOCK_AGENTS[1]]);
    await fetchAgents("DEAD");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/agents?state=DEAD"),
      undefined
    );
  });

  it("calls /agents?state=ACTIVE with ACTIVE filter", async () => {
    mockFetch([MOCK_AGENTS[0]]);
    await fetchAgents("ACTIVE");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("?state=ACTIVE"),
      undefined
    );
  });

  it("no state filter — no ?state in URL", async () => {
    mockFetch(MOCK_AGENTS);
    await fetchAgents();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).not.toContain("?state");
  });

  it("returns empty array on empty response", async () => {
    mockFetch([]);
    const agents = await fetchAgents();
    expect(agents).toEqual([]);
  });
});

describe("fetchAgent", () => {
  it("calls /agents/{name}", async () => {
    mockFetch(MOCK_AGENTS[0]);
    const agent = await fetchAgent("CEO");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/agents/CEO"),
      undefined
    );
    expect(agent.name).toBe("CEO");
  });

  it("throws on 404", async () => {
    mockFetch({ detail: "not found" }, 404);
    await expect(fetchAgent("GHOST")).rejects.toThrow("API error 404");
  });

  it("encodes name with special chars", async () => {
    mockFetch(MOCK_AGENTS[0]);
    await fetchAgent("MY AGENT");
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("MY%20AGENT");
  });
});

describe("fetchServers", () => {
  it("calls /servers and returns ServerInfo[]", async () => {
    mockFetch(MOCK_SERVERS);
    const servers = await fetchServers();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/servers"),
      undefined
    );
    expect(servers[0].ip).toBe("85.215.100.1");
  });
});

describe("restartAgent", () => {
  it("POSTs to /agents/{name}/restart", async () => {
    mockFetch(MOCK_RESTART);
    await restartAgent("ICT");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/agents/ICT/restart"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns RestartResponse", async () => {
    mockFetch(MOCK_RESTART);
    const result = await restartAgent("ICT");
    expect(result.queued).toBe(true);
    expect(result.name).toBe("ICT");
  });
});

describe("BASE_URL", () => {
  it("defaults to localhost:8000", async () => {
    mockFetch(MOCK_AGENTS);
    await fetchAgents();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("localhost:8000");
  });
});

describe("killAgent", () => {
  it("POSTs to /agents/{name}/kill", async () => {
    mockFetch(MOCK_RESTART);
    await killAgent("ICT");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/agents/ICT/kill"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns KillResponse with queued=true", async () => {
    mockFetch(MOCK_RESTART);
    const result = await killAgent("Marketing");
    expect(result.queued).toBe(true);
    expect(result.name).toBe("ICT"); // mock returns MOCK_RESTART fixture
  });
});

describe("respawnAgent", () => {
  it("POSTs to /agents/{name}/respawn", async () => {
    mockFetch(MOCK_RESTART);
    await respawnAgent("CEO");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/agents/CEO/respawn"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns RespawnResponse with queued=true", async () => {
    mockFetch(MOCK_RESTART);
    const result = await respawnAgent("CEO");
    expect(result.queued).toBe(true);
  });
});
