/**
 * useDeadAgentAlert — React hook that triggers browser Notifications
 * whenever the DEAD agent count increases.
 *
 * Features:
 *   - enabled toggle: call setEnabled(false) to suppress
 *   - permission guard: requests Notification permission on first enable
 *   - tag deduplication: one notification per unique dead-agent name
 *   - only fires on count increase (not on initial load)
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentInfo } from "./api";

export interface UseDeadAgentAlertOptions {
  /** Poll interval in ms (default 30_000) */
  pollMs?: number;
  /** Initial enabled state (default true) */
  initialEnabled?: boolean;
}

export interface UseDeadAgentAlertResult {
  enabled: boolean;
  setEnabled: (v: boolean) => void;
  deadCount: number;
  permissionGranted: boolean;
}

function getDeadNames(agents: AgentInfo[]): Set<string> {
  return new Set(agents.filter((a) => a.state === "DEAD").map((a) => a.name));
}

export function useDeadAgentAlert(
  agents: AgentInfo[],
  options: UseDeadAgentAlertOptions = {}
): UseDeadAgentAlertResult {
  const { initialEnabled = true } = options;

  const [enabled, setEnabledState] = useState(initialEnabled);
  const [permissionGranted, setPermissionGranted] = useState(
    typeof Notification !== "undefined" && Notification.permission === "granted"
  );

  const prevDeadRef = useRef<Set<string>>(new Set());
  const notifiedRef = useRef<Set<string>>(new Set());
  const initialRef = useRef(true);

  const requestPermission = useCallback(async () => {
    if (typeof Notification === "undefined") return false;
    if (Notification.permission === "granted") return true;
    if (Notification.permission === "denied") return false;
    const result = await Notification.requestPermission();
    const granted = result === "granted";
    setPermissionGranted(granted);
    return granted;
  }, []);

  const setEnabled = useCallback(
    async (v: boolean) => {
      if (v) {
        const ok = await requestPermission();
        setPermissionGranted(ok);
      }
      setEnabledState(v);
    },
    [requestPermission]
  );

  const deadNames = getDeadNames(agents);
  const deadCount = deadNames.size;

  useEffect(() => {
    if (initialRef.current) {
      // On first render: establish baseline, don't fire notifications
      prevDeadRef.current = deadNames;
      initialRef.current = false;
      return;
    }

    if (!enabled || !permissionGranted) return;

    for (const name of deadNames) {
      if (!prevDeadRef.current.has(name) && !notifiedRef.current.has(name)) {
        // New DEAD agent — fire deduplicated notification
        new Notification(`Agent DEAD: ${name}`, {
          body: `${name} is no longer responding.`,
          tag: `dead-agent-${name}`,
        });
        notifiedRef.current.add(name);
      }
    }

    // Clear notified cache for agents that recovered
    for (const name of notifiedRef.current) {
      if (!deadNames.has(name)) {
        notifiedRef.current.delete(name);
      }
    }

    prevDeadRef.current = deadNames;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents, enabled, permissionGranted]);

  return { enabled, setEnabled, deadCount, permissionGranted };
}
