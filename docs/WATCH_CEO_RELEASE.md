# Native CEO overview — 15 November 2026

Reference: watch-ceo-startscreen-20261115 / clawd GH#4192.

## Source and existing installation

The installed-app candidate is the preserved May 31 APK from netcup1:
`/home/claude/www/downloads/agent-terminals-watch-20260531-204209-4346a839304b.apk`.
SHA256: `8dff76d6f74e6b2ff5c84cf80d51a0b4e7632cf0bdc7ea456f58048b72d8c27f`.
Package: `com.spockymagicai.agentterminals`, version 1.0 / code 1.
This is a different package from the Capacitor app in `android/` (`com.spocky.agentterminals`).
The APK is a candidate based on its deployment and gateway; no physical-device package inspection was possible.

The original native source was absent from checked local and remote project directories. `native/` was recovered using jadx 1.5.3 from that APK. Anonymous-class references in TerminalActivity were repaired for compilation. Existing terminal destinations, device identity and certificate pin were retained. `gateway/` was recovered from the deployed signed gateway on netcup1 (`/opt/watch-gateway/app`). No new CEO session is created, restarted or killed by the new overview.

## Implemented core

Normal start opens the native overview on Watch or phone; the former launcher is now `TerminalsActivity`. The original terminal screen remains available. The overview shows connection/last sync, system-dictation entry, needs-input/running/unread-completed counts, task/query search, details, results and versioned replies. Dictation opens the installed Android speech activity; its transcript remains an editable draft until Send. No app-owned always-on microphone, audio upload or automatic audio playback.

Drafts and an atomic local outbox survive process death. Queued payloads and IDs are immutable across retries. A server 409 moves the original text to a review list, rather than blocking all later sends or silently discarding it. Unknown network outcomes remain queued. A server ACK is required before displaying accepted. Status-only phrases are sent as queries and excluded from task counters.

The shared signed HTTPS gateway adds:

- `POST /v1/ceo/requests`: text, stable `client_request_id`, kind `task` or `query`.
- `GET /v1/tasks`: shared authorized user's snapshot, tasks plus queries.
- `GET /v1/tasks/{id}`: authoritative detail and version.
- `POST /v1/tasks/{id}/replies`: request ID, text, `question_id`, `question_version`.

Every endpoint uses existing device request signatures and certificate pinning. SQLite acceptance, dedup response and CEO outbox entry commit together with synchronous=FULL. Same ID/content returns the original acceptance, changed content returns 409. Task/query IDs are UUIDs. Responses include accepted_at/status/version. No fabricated progress, agent assignment or start status. No public endpoint lets a client mark its task completed. Pause/cancel are not presented because no confirmed execution cancellation adapter exists.

Outbox delivery uses the existing `teammate send CEO` path; no spawn command. Delivery retries on command failure and remains accepted until the agent explicitly updates status. If a crash occurs after messaging and before marking delivery, a message may repeat; the same task ID is included and the CEO is instructed to check its stored status before execution. Exactly-once agent side effects are **not** claimed.

Existing allowed devices share one user's task store. Each new device still needs its public fingerprint approved through the existing enrollment procedure; no automatic access expansion was introduced. Android device signing material is encrypted at rest using an Android Keystore AES key; existing identity is migrated without changing its public fingerprint. Device backup is disabled.

## Agent updates (netcup1)

```
node /opt/watch-gateway/app/task-agent.js list
node /opt/watch-gateway/app/task-agent.js get TASK_ID
node /opt/watch-gateway/app/task-agent.js update TASK_ID '{"status":"in_progress","responsible_agent":"CEO","current_activity":"Prüfe den Auftrag"}'
node /opt/watch-gateway/app/task-agent.js update TASK_ID '{"status":"needs_input","question":"Welche Variante?"}'
node /opt/watch-gateway/app/task-agent.js update TASK_ID '{"status":"completed","result":"Das konkrete Ergebnis"}'
```

The local CLI and gateway share `gateway/state/tasks.sqlite` (or WATCH_TASK_DB). This database is not committed. It must be included in normal server backups. CLI access is trusted local OS access; it is not an externally accessible status-mutation API.

## Build and validation

`native/build.sh` builds without Gradle or third-party runtime libraries, using JDK21, Android platform36 and build-tools35.0.0. Minimum API26, target35, versionCode2 / 1.1-ceo. SDK/JDK paths and signing keys are external. The script uses WATCH_KEYSTORE/WATCH_KEY_ALIAS and env-based key/store passwords if supplied.

`native/test.sh` tests the same Outbox class used by the Activity with Android-compatible JSON: restart keeps request ID, wrong ACK retains queue, failed local commit retains queue, accepted ACK removes queue, stale reply quarantine retains text, status queries do not become execution tasks, and corrupt storage is not silently replaced. NotificationPolicy tests verify important-event-only notifications and version deduplication.

`npm test --prefix gateway`: existing signature/replay and session tests, task persistence/dedup/conflict, query IDs, stale question rejection, explicit completion/versioning, unavailable CEO retry and a real TLS subprocess integration test. The integration test kills/restarts only its isolated gateway process and uses a temporary database/keypair; it does not send commands to production agents. It verifies rejection without signature, acceptance/retry across restart, conflict, question, reply, result, and preserved five-session API.

Live on netcup1: watch-mtls-gateway restarted alone on 15 November; health=200, unsigned /v1/tasks=403. Existing server certificate pin matches recovered app configuration. Code backup before deployment: `/home/claude/backups/watch-20261115/gateway-before-ceo.tgz`. Real-device signed requests remain unverified.

`npm run test:native-protocol --prefix gateway` additionally compiles the real Java SecureGatewayClient, certificate pin verifier and fingerprint code against JVM adapters for Android Context/Base64/device-key access and a temporary endpoint configuration. The actual Java signing/HTTP/JSON code then talks to a real isolated Node gateway: UTF8, accepted ACK, stable retry, snapshot, 409 conflict and wrong TLS pin rejection all pass. These JVM adapters do not exercise the Android Keystore implementation, speech UI or actual device networking.

## Blocking installation issue

Original APK signing certificate SHA256:
`05a676fcc3b750ca7e8b57955394a2b9e8c7665249918277e4b836816b91de12`.
Available debug keystore certificate:
`f5d2b89aa89f7ac1c0ddea0a928379a1697ff47d7fc7618cd9ca3e5819b2980d`.
They differ. The built `native/build/agent-terminals-ceo-preview.apk` is **not an in-place update** for the preserved APK. The build script labels the mismatch and only emits an update APK when the certificate matches. Do not uninstall the old app or clear its data: this would lose its identity and require reenrollment. Find the original signing keystore or inspect the actual device package/certificate before choosing an installation route. No ADB device was connected; Windows build host SSH was unavailable.

## Remaining acceptance work

- Confirm the actual installed package/version and signing certificate on Watch and phone; install with matching signer.
- Real Watch/phone UI, larger fonts, system dictation availability/permissions, rotation/process death and Android Keystore migration tests.
- Real spoken request through existing CEO to result and follow-up on both devices. Gateway integration is tested; this hardware flow is not.
- True immediate push transport is not implemented. The battery-aware fallback uses Android JobScheduler every15min (system may delay), with runtime permission/settings, private lock-screen content, per-task/version dedup and local-only notifications to avoid phone mirroring duplicates. Foreground sync runs every30s and refreshes on opening. Background notifications need device/Doze tests; outbox delivery resumes in foreground, not in the background job.
- Terminal snapshot refresh now stops onPause and resumes onResume; returning to the overview does not keep terminal polling active. Existing terminal controls remain; no terminal interaction was tested against a live agent.
- Audio streaming/Whisper, Watch tile and optional read-aloud are later comfort scope.
- Hotspot/Tailscale forwarding and independent LTE/eSIM are unverified. No tariff was purchased or changed. Treat watch-lte-setup-20261115 separately.

This is a built and server-tested core, not a claim of completed device acceptance or the complete P1+P2 regular release.
