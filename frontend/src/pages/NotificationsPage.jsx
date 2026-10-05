import { formatDateTime } from "../config/dateTime";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import {
  actionLabelForNotification,
  categoryForNotificationType,
  destinationForNotification,
  formatNotificationType,
} from "../config/notificationPresentation";
import { useAuth } from "../context/AuthContext";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../services/api";

export default function NotificationsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = user?.role || "";
  const { refreshNotifications } = useOutletContext() || {};
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all"); // all | unread

  async function load({ silent = false } = {}) {
    if (!silent) {
      setLoading(true);
      setError("");
    }
    try {
      const data = await fetchNotifications(false);
      setItems(Array.isArray(data) ? data : []);
      if (refreshNotifications) await refreshNotifications();
    } catch {
      if (!silent) {
        setError("Unable to load notifications. Please try again.");
        setItems([]);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(() => load({ silent: true }), 8000);
    const onFocus = () => load({ silent: true });
    const onVisible = () => {
      if (document.visibilityState === "visible") onFocus();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const unreadCount = useMemo(
    () => items.filter((n) => !n.is_read).length,
    [items]
  );

  const visible = useMemo(() => {
    if (filter === "unread") return items.filter((n) => !n.is_read);
    return items;
  }, [items, filter]);

  const selected = items.find((n) => n.id === selectedId) || null;

  async function refreshBadge() {
    if (refreshNotifications) await refreshNotifications();
  }

  async function onMarkRead(id) {
    try {
      await markNotificationRead(id);
      setItems((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      await refreshBadge();
    } catch {
      setError("Unable to mark notification as read. Please try again.");
    }
  }

  async function onOpen(note) {
    setSelectedId(note.id);
    if (!note.is_read) {
      await onMarkRead(note.id);
    }
  }

  async function onOpenAndGo(note) {
    await onOpen(note);
    const dest = destinationForNotification(note, role);
    if (dest) {
      navigate(dest, {
        state: { from: "/app/notifications" },
      });
      return;
    }
    // No deep-link destination — keep detail panel open for context.
  }

  async function onMarkAll() {
    setBusy(true);
    setError("");
    try {
      await markAllNotificationsRead();
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      await refreshBadge();
    } catch {
      setError("Unable to mark all notifications as read. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const selectedAction = selected
    ? actionLabelForNotification(selected, role)
    : null;

  return (
    <div className="space-y-5">
      <PageHeader
        breadcrumb="Home / Notifications"
        title="Notifications"
        description={
          !loading && !error && unreadCount > 0
            ? `System alerts, workflow updates, and case-related notifications · ${unreadCount} unread.`
            : "System alerts, workflow updates, and case-related notifications."
        }
        actions={
          <>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <span className="sr-only">Filter notifications</span>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                aria-label="Filter notifications"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="all">All</option>
                <option value="unread">Unread only</option>
              </select>
            </label>
            <button
              type="button"
              disabled={busy || loading || !!error || unreadCount === 0}
              onClick={onMarkAll}
              className="btn-secondary"
            >
              {busy ? "Updating…" : "Mark all read"}
            </button>
          </>
        }
      />

      {error ? (
        <ErrorBanner
          title="Unable to load notifications."
          message={error}
          onRetry={() => load()}
        />
      ) : null}

      {loading ? (
        <LoadingState
          title="Loading notifications…"
          detail="Retrieving portal notifications."
        />
      ) : null}

      {!loading && !error ? (
        <div
          className={
            selected ? "portal-split" : "grid gap-4"
          }
        >
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            {visible.length === 0 ? (
          <EmptyState
            title={
              filter === "unread"
                ? "No unread notifications."
                : "No notifications on record."
            }
            detail={
              role === "STUDENT"
                ? "Notifications appear when a UFM case is filed or its status changes."
                : "Alerts appear when cases are filed, status changes, clarifications arrive, or detections are confirmed."
            }
          />
            ) : (
              <ul className="divide-y divide-slate-100" aria-label="Notification list">
                {visible.map((n) => {
                  const active = selectedId === n.id;
                  const unread = !n.is_read;
                  return (
                    <li key={n.id}>
                      <button
                        type="button"
                        onClick={() => onOpenAndGo(n)}
                        aria-current={active ? "true" : undefined}
                        className={[
                          "portal-option flex w-full flex-wrap items-start justify-between gap-3 border-l-4 px-5 py-4 text-left transition",
                          active
                            ? "border-l-au-blue bg-sky-100"
                            : unread
                              ? "border-l-sky-500 bg-sky-50/60 hover:border-l-au-blue hover:bg-sky-200"
                              : "border-l-transparent bg-white hover:border-l-au-blue hover:bg-sky-200",
                        ].join(" ")}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              {categoryForNotificationType(n.type)}
                            </p>
                            {unread ? (
                              <span className="rounded bg-au-navy px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                                Unread
                              </span>
                            ) : (
                              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                Read
                              </span>
                            )}
                          </div>
                          <p
                            className={[
                              "mt-1 text-au-navy",
                              unread ? "font-semibold" : "font-medium",
                            ].join(" ")}
                          >
                            {n.title}
                          </p>
                          <p className="mt-1 line-clamp-2 text-sm text-slate-600">
                            {n.message}
                          </p>
                          <p className="mt-2 text-xs text-slate-400">
                            {n.created_at
                              ? formatDateTime(n.created_at)
                              : ""}
                            {n.case_number
                              ? ` · ${n.case_number}`
                              : n.case_id
                                ? ` · Case #${n.case_id}`
                                : ""}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs font-semibold text-au-blue" aria-hidden="true">
                          →
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {selected ? (
            <aside
              className="portal-split-detail rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              aria-label="Notification details"
            >
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold text-au-navy">Details</h2>
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  className="text-xs font-semibold text-slate-500 hover:text-au-navy"
                >
                  Close
                </button>
              </div>
              <div className="mt-3 space-y-4 text-sm">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {categoryForNotificationType(selected.type)}
                    <span className="ml-2 font-normal normal-case text-slate-400">
                      · {formatNotificationType(selected.type)}
                    </span>
                  </p>
                  <p className="mt-1 text-lg font-semibold text-au-navy">
                    {selected.title}
                  </p>
                  <p className="mt-2 whitespace-pre-wrap text-slate-700">
                    {selected.message}
                  </p>
                </div>

                {selected.case_id ? (
                  <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">
                      Linked UFM case
                    </p>
                    <p className="font-semibold text-au-navy">
                      {selected.case_number || `Case #${selected.case_id}`}
                    </p>
                    {selected.case_violation ? (
                      <p className="text-slate-600">
                        {String(selected.case_violation).replaceAll("_", " ")}
                      </p>
                    ) : null}
                    {selected.case_status ? (
                      <StatusBadge status={selected.case_status} />
                    ) : null}
                  </div>
                ) : selected.type === "DETECTION_ALERT" &&
                  role !== "STUDENT" ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-600">
                    Related to a confirmed detection. Open Detections to review.
                  </div>
                ) : null}

                <p className="text-xs text-slate-400">
                  {selected.created_at
                    ? formatDateTime(selected.created_at)
                    : ""}
                  {selected.is_read ? " · Read" : " · Unread"}
                </p>

                <div className="flex flex-wrap gap-2">
                  {selectedAction ? (
                    <button
                      type="button"
                      onClick={() => onOpenAndGo(selected)}
                      className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
                    >
                      {selectedAction}
                    </button>
                  ) : null}
                  {selected.case_id ? (
                    <Link
                      to={`/app/cases/${selected.case_id}`}
                      state={{ from: "/app/notifications" }}
                      className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
                    >
                      Case detail
                    </Link>
                  ) : null}
                  {!selected.is_read ? (
                    <button
                      type="button"
                      onClick={() => onMarkRead(selected.id)}
                      className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
                    >
                      Mark read
                    </button>
                  ) : null}
                </div>
              </div>
            </aside>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
