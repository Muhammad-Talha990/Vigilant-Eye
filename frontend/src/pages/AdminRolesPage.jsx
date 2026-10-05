import { useEffect, useState } from "react";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { fetchAdminRoles, fetchAdminUserStats } from "../services/api";

export default function AdminRolesPage() {
  const [roles, setRoles] = useState([]);
  const [byRole, setByRole] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [data, stats] = await Promise.all([
          fetchAdminRoles(),
          fetchAdminUserStats(),
        ]);
        if (!cancelled) {
          setRoles(Array.isArray(data) ? data : []);
          setByRole(stats?.by_role || {});
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load roles");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Administration / Roles"
        title="Roles & Permissions"
        description="Roles and permissions of VigilantEye users."
      />
      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {loading ? <LoadingState label="Loading role catalog…" /> : null}

      {!loading && roles.length === 0 && !error ? (
        <p className="text-sm text-slate-500">No role catalog entries returned.</p>
      ) : null}

      {!loading && roles.length > 0 ? (
        <div className="portal-table-wrap rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="portal-table">
            <thead className="border-b bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Users</th>
                <th className="px-4 py-3">Main access areas</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((r) => (
                <tr key={r.role} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-3">
                    <p className="font-semibold text-au-navy">{r.title}</p>
                    <code className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                      {r.role}
                    </code>
                    <p className="mt-2 text-xs text-slate-500">{r.summary}</p>
                  </td>
                  <td className="px-4 py-3 text-lg font-semibold text-au-navy">
                    {byRole[r.role] ?? 0}
                  </td>
                  <td className="px-4 py-3">
                    <ul className="list-disc space-y-1 pl-5 text-slate-700">
                      {(r.can || []).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    {(r.cannot || []).length ? (
                      <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-rose-700">
                        Not included
                      </p>
                    ) : null}
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-slate-500">
                      {(r.cannot || []).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
