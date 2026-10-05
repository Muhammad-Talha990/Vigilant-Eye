import { useCallback, useEffect, useState } from "react";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { fetchAdminStudents } from "../services/api";

export default function AdminStudentsPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [linked, setLinked] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const pageSize = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminStudents({
        page,
        page_size: pageSize,
        q: q.trim() || undefined,
        linked: linked || undefined,
      });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message || "Failed to load student directory");
    } finally {
      setLoading(false);
    }
  }, [page, q, linked]);

  useEffect(() => {
    load();
  }, [load]);

  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Administration / Students"
        title="Student Directory"
        description="Institutional student records for access management. Read-only directory view."
      />

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="min-w-[12rem] flex-1 text-sm">
          <span className="mb-1 block text-slate-600">Search</span>
          <input
            className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
            placeholder="Roll, name, department…"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Portal link</span>
          <select
            className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm"
            value={linked}
            onChange={(e) => {
              setPage(1);
              setLinked(e.target.value);
            }}
          >
            <option value="">Any</option>
            <option value="linked">Linked to portal user</option>
            <option value="unlinked">Unlinked</option>
          </select>
        </label>
        <button
          type="button"
          className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700"
          onClick={() => {
            setQ("");
            setLinked("");
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
      {loading ? <LoadingState label="Loading students…" /> : null}

      {!loading ? (
        <div className="portal-table-wrap rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="portal-table">
            <thead className="border-b bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Student name</th>
                <th className="px-3 py-2">Roll number</th>
                <th className="px-3 py-2">Department</th>
                <th className="px-3 py-2">Program</th>
                <th className="px-3 py-2">Linked Google email</th>
                <th className="px-3 py-2">Portal status</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                    No student records match.
                  </td>
                </tr>
              ) : (
                items.map((s) => (
                  <tr key={s.id} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-medium text-au-navy">{s.name}</td>
                    <td className="px-3 py-2">{s.student_id}</td>
                    <td className="px-3 py-2">{s.department}</td>
                    <td className="px-3 py-2">{s.program}</td>
                    <td className="px-3 py-2">
                      {s.linked_email || (s.user_id != null ? `user #${s.user_id}` : "—")}
                    </td>
                    <td className="px-3 py-2">
                      {s.user_id == null ? (
                        <span className="text-slate-400">Unlinked</span>
                      ) : s.portal_active ? (
                        <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                          Active · {s.portal_role || "STUDENT"}
                        </span>
                      ) : (
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                          Inactive · {s.portal_role || "STUDENT"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t px-3 py-2 text-sm text-slate-600">
            <span>
              {total} record{total === 1 ? "" : "s"} · page {page}/{pages}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border px-3 py-1 disabled:opacity-40"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <button
                type="button"
                className="rounded border px-3 py-1 disabled:opacity-40"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
