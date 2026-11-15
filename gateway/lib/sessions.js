const sessions = [
  { id: "ceo", name: "CEO", tmuxName: "CEO", targetHost: "100.65.150.128", targetPort: 7681, server: "netcup1", sshHost: null },
  { id: "marketing", name: "Marketing", tmuxName: "Marketing", targetHost: "100.112.209.61", targetPort: 7682, server: "hetzner", sshHost: "hetzner" },
  { id: "strategy", name: "Strategy", tmuxName: "Strategy", targetHost: "100.84.243.76", targetPort: 7683, server: "hostinger", sshHost: "hostinger" },
  { id: "operations", name: "Operations", tmuxName: "Operations", targetHost: "100.113.46.3", targetPort: 7684, server: "netcup2", sshHost: "netcup2" },
  { id: "ict", name: "ICT", tmuxName: "ICT", targetHost: "100.65.150.128", targetPort: 7685, server: "netcup1", sshHost: null },
];

function publicSessions() {
  return sessions.map(({ id, name, server }) => ({ id, name, server }));
}

function findSession(id) {
  return sessions.find((session) => session.id === id);
}

module.exports = {
  findSession,
  publicSessions,
  sessions,
};
