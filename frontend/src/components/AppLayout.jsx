import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { DETECTION_ROLES, roleIn } from "../config/roleAccess";
import { API_URL, fetchDetections, fetchNotifications } from "../services/api";
import { useAuth } from "../context/AuthContext";
import Header from "./Header";
import Sidebar from "./Sidebar";

function wsAlertsUrl(token) {
  const base = (API_URL || "http://127.0.0.1:8000").replace(/^http/, "ws");
  const params = new URLSearchParams({ token: token || "" });
  return `${base}/ws/alerts?${params.toString()}`;
}

export default function AppLayout() {
  const { user, token } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [unseenDetections, setUnseenDetections] = useState(0);
  const [livePulse, setLivePulse] = useState(null);

  const showDetectionBadge = roleIn(user?.role, DETECTION_ROLES);

  async function loadBadges() {
    try {
      const unread = await fetchNotifications(true);
      setUnreadCount(Array.isArray(unread) ? unread.length : 0);
    } catch {
      setUnreadCount(0);
    }
    if (showDetectionBadge) {
      try {
        const unseen = await fetchDetections(true, true);
        setUnseenDetections(Array.isArray(unseen) ? unseen.length : 0);
      } catch {
        setUnseenDetections(0);
      }
    } else {
      setUnseenDetections(0);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (cancelled) return;
      await loadBadges();
    })();
    const timer = setInterval(() => {
      if (!cancelled) loadBadges();
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [user?.role, showDetectionBadge]);

  // WebSocket push for monitoring/detection roles (C26)
  useEffect(() => {
    if (!token || !user) return undefined;
    if (!roleIn(user.role, DETECTION_ROLES)) {
      return undefined;
    }
    let ws;
    let closed = false;
    let retry;
    let authFailed = false;
    function connect() {
      if (closed || authFailed) return;
      try {
        ws = new WebSocket(wsAlertsUrl(token));
      } catch {
        retry = setTimeout(connect, 5000);
        return;
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (
            msg.type === "DETECTION_ALERT" ||
            msg.type === "DETECTION_ALERT_DEMO" ||
            msg.type === "SUSPICION_ALERT" ||
            msg.type === "CONNECTED"
          ) {
            if (msg.type !== "CONNECTED") {
              setLivePulse(msg);
              loadBadges();
            }
          }
        } catch {
          /* ignore */
        }
      };
      ws.onclose = (ev) => {
        // 4401/4403 = auth rejection — do not reconnect storm
        if (ev.code === 4401 || ev.code === 4403) {
          authFailed = true;
          return;
        }
        if (!closed) retry = setTimeout(connect, 4000);
      };
    }
    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      try {
        ws?.close();
      } catch {
        /* ignore */
      }
    };
  }, [token, user?.role]);

  const badges = {
    notifications: unreadCount,
    detections: unseenDetections,
  };

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-au-surface">
      <Header
        unreadCount={unreadCount}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      {livePulse ? (
        <div
          className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-xs text-amber-900"
          role="status"
          aria-live="polite"
        >
          Live alert: {livePulse.type}
          {livePulse.label ? ` · ${livePulse.label}` : ""}
          {livePulse.level ? ` · ${livePulse.level}` : ""}
          {livePulse.score != null ? ` · score ${livePulse.score}` : ""}
          <button
            type="button"
            className="ml-3 font-semibold underline"
            onClick={() => setLivePulse(null)}
            aria-label="Dismiss live alert"
          >
            Dismiss
          </button>
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1">
        <Sidebar
          open={sidebarOpen}
          badges={badges}
          onNavigate={() => setSidebarOpen(false)}
        />
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <div className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
            <Outlet
              context={{
                refreshNotifications: async () => {
                  try {
                    const unread = await fetchNotifications(true);
                    setUnreadCount(Array.isArray(unread) ? unread.length : 0);
                  } catch {
                    /* ignore */
                  }
                },
                refreshDetectionsBadge: async () => {
                  if (!showDetectionBadge) return;
                  try {
                    const unseen = await fetchDetections(true, true);
                    setUnseenDetections(Array.isArray(unseen) ? unseen.length : 0);
                  } catch {
                    /* ignore */
                  }
                },
              }}
            />
          </div>
        </main>
      </div>
    </div>
  );
}
