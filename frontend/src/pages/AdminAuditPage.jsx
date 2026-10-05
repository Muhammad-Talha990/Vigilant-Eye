import { formatDateTime } from "../config/dateTime";
import { useCallback, useEffect, useState } from "react";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { fetchAdminAuditLogs } from "../services/api";

const ACTION_OPTIONS = [
  "",
  "USER_CREATED",
  "USER_ROLE_CHANGED",
  "USER_DEACTIVATED",
  "USER_REACTIVATED",
  "USER_STUDENT_LINKED",
  "USER_STUDENT_UNLINKED",
  "USER_BULK_IMPORTED",
];

const PAGE_SIZE = 25;

export default function AdminAuditPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminAuditLogs({
        q: q.trim() || undefined,
        action: action || undefined,
        user_admin_only: true,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message || "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [q, action, page]);

  useEffect(() => {
    load();
  }, [load]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Administration / Audit"
        title="Security and Audit"
        description="Administrative audit log for user-management actions."
      />

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="min-w-[12rem] flex-1 text-sm">
          <span className="mb-1 block text-slate-600">Search description</span>
          <input
            className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
            placeholder="email, role, import…"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Action</span>
          <select
            className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm"
            value={action}
            onChange={(e) => {
              setPage(1);
              setAction(e.target.value);
            }}
          >
            {ACTION_OPTIONS.map((a) => (
              <option key={a || "all"} value={a}>
                {a || "All user-admin actions"}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="rounded-lg bg-au-navy px-4 py-2.5 text-sm font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-au-navy"
          onClick={() => {
            setPage(1);
            load();
          }}
        >
          Apply
        </button>
        <button
          type="button"
          className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700"
          onClick={() => {
            setQ("");
            setAction("");
            setPage(1);
          }}
        >
          Clear filters
        </button>
      </div>

      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {loading ? <LoadingState label="Loading audit logs…" /> : null}

      {!loading ? (
        <>
          <div className="portal-data-cards rounded-xl border border-slate-200 bg-white shadow-sm">
            {items.length === 0 ? (
              <p className="px-4 py-8 text-center text-slate-500">
                No matching audit events ({total} total in filter scope).
              </p>
            ) : (
              items.map((row) => (
                <div key={row.id} className="portal-case-card" data-affordance="static">
                  <div className="flex items-start justify-between gap-2">
                    <p className="portal-case-card-title">{row.action}</p>
                    <span className="text-xs text-slate-500">
                      {row.timestamp
                        ? formatDateTime(row.timestamp)
                        : "—"}
                    </span>
                  </div>
                  <p className="portal-case-card-meta">
                    {row.actor_email ||
                      (row.user_id ? `#${row.user_id}` : "system")}
                    {row.entity_id != null ? ` · Target #${row.entity_id}` : ""}
                  </p>
                  <details className="mt-2 text-sm text-slate-700">
                    <summary className="cursor-pointer font-medium text-au-navy">
                      Details
                    </summary>
                    <p className="mt-1 whitespace-pre-wrap break-words">
                      {row.description || "—"}
                    </p>
                  </details>
                </div>
              ))
            )}
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="portal-table-wrap portal-table-desktop">
              <table className="portal-table">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Timestamp</th>
                    <th className="px-3 py-2">Actor</th>
                    <th className="px-3 py-2">Action</th>
                    <th className="px-3 py-2 col-hide-md">Target user</th>
                    <th className="px-3 py-2">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-3 py-8 text-center text-slate-500"
                      >
                        No matching audit events ({total} total in filter
                        scope).
                      </td>
                    </tr>
                  ) : (
                    items.map((row) => (
                      <tr key={row.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 text-xs text-slate-500">
                          {row.timestamp
                            ? formatDateTime(row.timestamp)
                            : "—"}
                        </td>
                        <td className="px-3 py-2 cell-wrap">
                          {row.actor_email ||
                            (row.user_id ? `#${row.user_id}` : "system")}
                        </td>
                        <td className="px-3 py-2 font-medium text-au-navy">
                          {row.action}
                        </td>
                        <td className="px-3 py-2 col-hide-md">
                          {row.entity_id != null ? `#${row.entity_id}` : "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          <details>
                            <summary className="cursor-pointer text-xs font-medium text-au-blue">
                              <span className="line-clamp-2 inline text-slate-600">
                                {row.description
                                  ? row.description.length > 90
                                    ? `${row.description.slice(0, 90)}…`
                                    : row.description
                                  : "—"}
                              </span>
                            </summary>
                            <p className="mt-1 whitespace-pre-wrap break-words text-sm">
                              {row.description || "—"}
                            </p>
                          </details>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3 text-sm text-slate-600">
              <span>
                {total} event{total === 1 ? "" : "s"} · page {page} of {pages}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="rounded border border-slate-300 px-3 py-1 disabled:opacity-40"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="rounded border border-slate-300 px-3 py-1 disabled:opacity-40"
                  disabled={page >= pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
