import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../services/api";

function destinationFor(note) {
  if (note.case_id) return `/app/cases/${note.case_id}`;
  if (note.type === "DETECTION_ALERT") return "/app/detections";
  if (note.type === "RESULT_HOLD") return "/app/result-controls";
  return null;
}

function typeLabel(type) {
  return String(type || "NOTICE").replaceAll("_", " ");
}

export default function NotificationsPage() {
  const navigate = useNavigate();
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
    } catch (err) {
      if (!silent) setError(err.message || "Failed to load notifications");
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(() => load({ silent: true }), 4000);
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
    } catch (err) {
      setError(err.message || "Could not mark as read");
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
    const dest = destinationFor(note);
    if (dest) navigate(dest);
  }

  async function onMarkAll() {
    setBusy(true);
    setError("");
    try {
      await markAllNotificationsRead();
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      await refreshBadge();
    } catch (err) {
      setError(err.message || "Could not mark all as read");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Home / Notifications</p>
          <h1 className="text-2xl font-semibold text-au-navy">
            Notifications
            <span className="ml-2 align-middle text-[10px] font-bold uppercase tracking-wide text-emerald-700">
              Live
            </span>
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Updates automatically — new alerts show within a few seconds.
            {unreadCount > 0 ? (
              <span className="ml-1 font-semibold text-au-navy">
                {unreadCount} unread
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="all">All</option>
            <option value="unread">Unread only</option>
          </select>
          <button
            type="button"
            disabled={busy || unreadCount === 0}
            onClick={onMarkAll}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            Mark all read
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div
        className={
          selected
            ? "grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]"
            : "grid gap-4"
        }
      >
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          {loading ? (
            <p className="p-6 text-slate-500">Loading...</p>
          ) : visible.length === 0 ? (
            <div className="space-y-2 p-8 text-center">
              <p className="text-lg font-semibold text-au-navy">
                {filter === "unread" ? "No unread notifications" : "Inbox clear"}
              </p>
              <p className="text-sm text-slate-600">
                Alerts appear when cases are filed, status changes, clarifications
                arrive, or AI detections are confirmed.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {visible.map((n) => {
                const active = selectedId === n.id;
                return (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => onOpen(n)}
                      className={[
                        "flex w-full flex-wrap items-start justify-between gap-3 px-5 py-4 text-left transition",
                        active
                          ? "bg-sky-100/80"
                          : n.is_read
                            ? "bg-white hover:bg-slate-50"
                            : "bg-sky-50/70 hover:bg-sky-50",
                      ].join(" ")}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          {typeLabel(n.type)}
                          {!n.is_read ? (
                            <span className="ml-2 rounded bg-red-500 px-1.5 py-0.5 text-[10px] text-white">
                              NEW
                            </span>
                          ) : null}
                        </p>
                        <p className="mt-1 font-semibold text-au-navy">{n.title}</p>
                        <p className="mt-1 line-clamp-2 text-sm text-slate-600">
                          {n.message}
                        </p>
                        <p className="mt-2 text-xs text-slate-400">
                          {n.created_at
                            ? new Date(n.created_at).toLocaleString()
                            : ""}
                          {n.case_number
                            ? ` · ${n.case_number}`
                            : n.case_id
                              ? ` · Case #${n.case_id}`
                              : ""}
                        </p>
                      </div>
                      <span className="shrink-0 text-xs font-semibold text-au-blue">
                        View
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {selected ? (
          <aside className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:sticky lg:top-4 lg:self-start">
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
                  {typeLabel(selected.type)}
                </p>
                <p className="mt-1 text-lg font-semibold text-au-navy">
                  {selected.title}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-slate-700">
                  {selected.message}
                </p>
              </div>

              {selected.case_id ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
                  <p className="text-xs font-semibold uppercase text-slate-500">
                    Linked case
                  </p>
                  <p className="font-semibold text-au-navy">
                    {selected.case_number || `Case #${selected.case_id}`}
                  </p>
                  {selected.case_violation ? (
                    <p className="text-slate-600">{selected.case_violation}</p>
                  ) : null}
                  {selected.case_status ? (
                    <StatusBadge status={selected.case_status} />
                  ) : null}
                </div>
              ) : selected.type === "DETECTION_ALERT" ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-600">
                  Related to a confirmed AI detection. Open Detections to review
                  and create a case if needed.
                </div>
              ) : null}

              <p className="text-xs text-slate-400">
                {selected.created_at
                  ? new Date(selected.created_at).toLocaleString()
                  : ""}
              </p>

              <div className="flex flex-wrap gap-2">
                {destinationFor(selected) ? (
                  <button
                    type="button"
                    onClick={() => onOpenAndGo(selected)}
                    className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
                  >
                    {selected.case_id
                      ? "Open case"
                      : selected.type === "RESULT_HOLD"
                        ? "Open result controls"
                        : "Open detections"}
                  </button>
                ) : null}
                {selected.case_id ? (
                  <Link
                    to={`/app/cases/${selected.case_id}`}
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
    </div>
  );
}
