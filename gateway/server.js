const fs = require("fs");
const crypto = require("crypto");
const https = require("https");
const http = require("http");
const { execFile } = require("child_process");
const {
  cookieValue,
  parseAllowlist,
  signSessionToken,
  verifySessionToken,
  verifySignedRequest,
} = require("./lib/auth");
const { findSession, publicSessions } = require("./lib/sessions");

const listenHost = process.env.WATCH_GATEWAY_HOST || "0.0.0.0";
const listenPort = Number(process.env.WATCH_GATEWAY_PORT || 9443);
const certPath = process.env.WATCH_GATEWAY_CERT || "/opt/watch-gateway/server.crt";
const keyPath = process.env.WATCH_GATEWAY_KEY || "/opt/watch-gateway/server.key";
const allowlist = parseAllowlist(process.env.WATCH_GATEWAY_ALLOWED_FINGERPRINTS || "");
const sessionSecret = process.env.WATCH_GATEWAY_SESSION_SECRET || "dev-only-change-me";
const nonceCache = new Map();
const launchTokens = new Map();

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
    "cache-control": "no-store",
  });
  res.end(payload);
}

function sendText(res, status, body, headers = {}) {
  res.writeHead(status, {
    "content-type": "text/plain; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
    ...headers,
  });
  res.end(body);
}

function readBody(req, callback) {
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => callback(Buffer.concat(chunks)));
  req.on("error", () => callback(null));
}

function runCommand(file, args, options = {}) {
  return new Promise((resolve) => {
    execFile(file, args, {
      timeout: options.timeout || 8000,
      maxBuffer: options.maxBuffer || 1024 * 1024,
    }, (error, stdout, stderr) => {
      resolve({
        ok: !error,
        code: error && typeof error.code === "number" ? error.code : 0,
        error: error ? error.message : "",
        stdout: stdout || "",
        stderr: stderr || "",
      });
    });
  });
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function tmuxCommand(session, command) {
  if (!session.sshHost) {
    return runCommand("bash", ["-lc", command]);
  }
  return runCommand("ssh", [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=5",
    session.sshHost,
    command,
  ]);
}

async function captureTmux(session) {
  const target = shellQuote(session.tmuxName);
  const command = `tmux has-session -t ${target} && tmux capture-pane -t ${target} -p -S -120`;
  return tmuxCommand(session, command);
}

async function sendTmuxInput(session, text, enter) {
  const target = shellQuote(session.tmuxName);
  const encoded = Buffer.from(String(text || ""), "utf8").toString("base64");
  const parts = [
    `tmux has-session -t ${target}`,
  ];
  if (encoded) {
    parts.push(`printf %s ${shellQuote(encoded)} | base64 -d | tmux load-buffer -`);
    parts.push(`tmux paste-buffer -t ${target}`);
  }
  if (enter) {
    parts.push(`tmux send-keys -t ${target} Enter`);
  }
  return tmuxCommand(session, parts.join(" && "));
}

const server = https.createServer(
  {
    key: fs.readFileSync(keyPath),
    cert: fs.readFileSync(certPath),
    requestCert: true,
    rejectUnauthorized: false,
  },
  (req, res) => {
    if (req.url.startsWith("/launch/")) {
      launchRoute(req, res);
      return;
    }

    if (req.url.startsWith("/terminal/")) {
      terminalRoute(req, res);
      return;
    }

    if (req.url === "/health") {
      sendJson(res, 200, { ok: true });
      return;
    }

    readBody(req, (body) => {
      if (body === null) {
        sendJson(res, 400, { ok: false, error: "request_read_failed" });
        return;
      }

      const auth = verifySignedRequest(req, body, allowlist, nonceCache);
      if (!auth.ok) {
        sendJson(res, auth.status, {
          ok: false,
          error: auth.error,
          fingerprint: auth.fingerprint || null,
        });
        return;
      }

      if (req.url === "/api/sessions") {
        sendJson(res, 200, { ok: true, sessions: publicSessions() });
        return;
      }

      const parsedPath = new URL(req.url, "https://watch-gateway.local").pathname;

      if (parsedPath.startsWith("/api/web-session/")) {
        const id = decodeURIComponent(parsedPath.replace("/api/web-session/", ""));
        const session = findSession(id);
        if (!session) {
          sendJson(res, 404, { ok: false, error: "unknown_session" });
          return;
        }
        const exp = Math.floor(Date.now() / 1000) + 3600;
        const token = signSessionToken({ fp: auth.fingerprint, exp, id }, sessionSecret);
        const launchToken = crypto.randomBytes(32).toString("base64url");
        launchTokens.set(launchToken, { id, token, exp });
        cleanupLaunchTokens();
        sendJson(res, 200, {
          ok: true,
          launchPath: `/launch/${encodeURIComponent(id)}?token=${encodeURIComponent(launchToken)}`,
          expiresAt: exp,
        });
        return;
      }

      if (parsedPath.startsWith("/api/terminal/") && parsedPath.endsWith("/snapshot")) {
        const id = decodeURIComponent(parsedPath.replace("/api/terminal/", "").replace("/snapshot", "").replace(/\/$/, ""));
        const session = findSession(id);
        if (!session) {
          sendJson(res, 404, { ok: false, error: "unknown_session" });
          return;
        }
        captureTmux(session).then((result) => {
          if (!result.ok) {
            sendJson(res, 502, {
              ok: false,
              error: "tmux_capture_failed",
              details: (result.stderr || result.error).slice(0, 2000),
            });
            return;
          }
          sendJson(res, 200, {
            ok: true,
            session: id,
            server: session.server,
            text: result.stdout,
            capturedAt: new Date().toISOString(),
          });
        });
        return;
      }

      if (parsedPath.startsWith("/api/terminal/") && parsedPath.endsWith("/send")) {
        const id = decodeURIComponent(parsedPath.replace("/api/terminal/", "").replace("/send", "").replace(/\/$/, ""));
        const session = findSession(id);
        if (!session) {
          sendJson(res, 404, { ok: false, error: "unknown_session" });
          return;
        }
        let input;
        try {
          input = JSON.parse(body.toString("utf8") || "{}");
        } catch (error) {
          sendJson(res, 400, { ok: false, error: "invalid_json" });
          return;
        }
        const text = String(input.text || "");
        if (text.length > 2000) {
          sendJson(res, 413, { ok: false, error: "input_too_large" });
          return;
        }
        sendTmuxInput(session, text, Boolean(input.enter)).then((result) => {
          if (!result.ok) {
            sendJson(res, 502, {
              ok: false,
              error: "tmux_send_failed",
              details: (result.stderr || result.error).slice(0, 2000),
            });
            return;
          }
          sendJson(res, 200, { ok: true, session: id, server: session.server });
        });
        return;
      }

      sendJson(res, 404, { ok: false, error: "not_found" });
    });
  }
);

function cleanupLaunchTokens(nowSeconds = Math.floor(Date.now() / 1000)) {
  for (const [key, value] of launchTokens) {
    if (!value.exp || value.exp < nowSeconds) launchTokens.delete(key);
  }
}

function launchRoute(req, res) {
  const parsed = new URL(req.url, "https://watch-gateway.local");
  const match = parsed.pathname.match(/^\/launch\/([^/]+)$/);
  const tokenId = parsed.searchParams.get("token") || "";
  const launch = launchTokens.get(tokenId);
  launchTokens.delete(tokenId);
  cleanupLaunchTokens();

  if (!match || !launch) {
    sendText(res, 403, "launch token invalid or expired");
    return;
  }

  const id = decodeURIComponent(match[1]);
  if (id !== launch.id || !findSession(id)) {
    sendText(res, 403, "launch token session mismatch");
    return;
  }

  res.writeHead(302, {
    "cache-control": "no-store",
    "set-cookie": [
      `watch_session=${launch.token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=3600`,
      `watch_terminal=${encodeURIComponent(id)}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=3600`,
    ],
    location: `/terminal/${encodeURIComponent(id)}/`,
  });
  res.end();
}

function authorizeBrowser(req) {
  const token = cookieValue(req, "watch_session");
  return verifySessionToken(token, sessionSecret).ok;
}

function rewriteLocation(location, id) {
  if (!location) return location;
  if (location.startsWith("/")) return `/terminal/${id}${location}`;
  return location;
}

function proxyHttp(req, res, id, session, upstreamPath) {
  const upstream = http.request(
    {
      host: session.targetHost,
      port: session.targetPort,
      method: req.method,
      path: upstreamPath,
      headers: {
        ...req.headers,
        host: `${session.targetHost}:${session.targetPort}`,
      },
    },
    (upstreamRes) => {
      const headers = { ...upstreamRes.headers };
      if (headers.location) headers.location = rewriteLocation(headers.location, id);
      delete headers["content-security-policy"];
      res.writeHead(upstreamRes.statusCode || 502, headers);
      upstreamRes.pipe(res);
    }
  );
  upstream.on("error", (error) => sendText(res, 502, `terminal proxy error: ${error.message}`));
  req.pipe(upstream);
}

function terminalRoute(req, res) {
  if (!authorizeBrowser(req)) {
    sendText(res, 403, "watch session required");
    return;
  }
  const resolved = resolveTerminalRequest(req);
  if (!resolved) {
    sendText(res, 404, "terminal not found");
    return;
  }
  proxyHttp(req, res, resolved.id, resolved.session, resolved.upstreamPath);
}

function resolveTerminalRequest(req) {
  const parsed = new URL(req.url, "https://watch-gateway.local");
  let id = "";
  let upstreamPath = parsed.pathname;
  const match = parsed.pathname.match(/^\/terminal\/([^/]+)(\/.*)?$/);
  if (match) {
    id = decodeURIComponent(match[1]);
    upstreamPath = match[2] || "/";
  } else {
    id = cookieValue(req, "watch_terminal");
  }
  const session = findSession(id);
  if (!session) return null;
  return { id, session, upstreamPath: `${upstreamPath}${parsed.search}` };
}

server.on("upgrade", (req, socket, head) => {
  if (!authorizeBrowser(req)) {
    socket.write("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
    socket.destroy();
    return;
  }
  const resolved = resolveTerminalRequest(req);
  if (!resolved) {
    socket.write("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n");
    socket.destroy();
    return;
  }
  const upstream = http.request({
    host: resolved.session.targetHost,
    port: resolved.session.targetPort,
    method: req.method,
    path: resolved.upstreamPath,
    headers: {
      ...req.headers,
      host: `${resolved.session.targetHost}:${resolved.session.targetPort}`,
    },
  });
  upstream.on("upgrade", (upstreamRes, upstreamSocket, upstreamHead) => {
    socket.write(
      `HTTP/1.1 ${upstreamRes.statusCode} ${upstreamRes.statusMessage}\r\n` +
        Object.entries(upstreamRes.headers).map(([k, v]) => `${k}: ${v}`).join("\r\n") +
        "\r\n\r\n"
    );
    if (upstreamHead.length) socket.write(upstreamHead);
    if (head.length) upstreamSocket.write(head);
    upstreamSocket.pipe(socket).pipe(upstreamSocket);
  });
  upstream.on("error", () => {
    socket.write("HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n");
    socket.destroy();
  });
  upstream.end();
});

server.listen(listenPort, listenHost, () => {
  console.log(`watch gateway listening on https://${listenHost}:${listenPort}`);
  console.log(`allowed client fingerprints: ${allowlist.size}`);
});
