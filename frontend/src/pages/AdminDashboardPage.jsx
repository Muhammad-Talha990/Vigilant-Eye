import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ActionNavCard from "../components/ActionNavCard";
import KpiCard from "../components/KpiCard";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { ROLE_LABELS } from "../config/navByRole";
import { formatDateTime } from "../config/dateTime";

import {
  fetchAdminAuditLogs,
  fetchAdminUserStats,
} from "../services/api";

const QUICK = [
  { to: "/app/admin/users", label: "Manage Users", hint: "Open user directory →" },
  { to: "/app/admin/users?create=1", label: "+ Add User", hint: "Create a portal account →" },
  { to: "/app/admin/import", label: "Import Users", hint: "Bulk CSV import →" },
  { to: "/app/admin/students", label: "Student Directory", hint: "View linked students →" },
  { to: "/app/admin/roles", label: "Roles & Permissions", hint: "Review role catalog →" },
  { to: "/app/admin/audit", label: "Security and Audit", hint: "View audit history →" },
];

const ROLE_ORDER = [
  "STUDENT",
  "INVIGILATOR",
  "HOD",
  "DEC",
  "EXAM_DEPARTMENT",
  "UFM_COMMITTEE",
  "ADMINISTRATOR",
];

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const [st, logs] = await Promise.all([
          fetchAdminUserStats(),
          fetchAdminAuditLogs({ limit: 8, user_admin_only: true }),
        ]);
        if (cancelled) return;
        setStats(st);
        setActivity(logs.items || []);
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load administrator dashboard");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const by = stats?.by_role || {};

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Administration"
        title="System Administration"
        description="Manage system users, access, configuration, and administrative controls."
      />

      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {loading ? <LoadingState label="Loading administrator metrics…" /> : null}

      {!loading && stats ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <KpiCard title="Total users" value={stats.total} hint="Authorized portal accounts" accent="border-l-slate-600" />
            <KpiCard title="Active" value={stats.active} hint={`${stats.inactive} inactive`} accent="border-l-emerald-500" />
            <KpiCard title="Inactive" value={stats.inactive} hint="Cannot Google sign-in" accent="border-l-amber-500" />
            <KpiCard title="Students" value={by.STUDENT || 0} hint={`${stats.students_linked} linked`} accent="border-l-sky-500" />
            <KpiCard title="Administrators" value={by.ADMINISTRATOR || 0} hint="Portal admins" accent="border-l-violet-500" />
          </div>

          <section aria-label="Quick actions" className="space-y-2">
            <p className="portal-action-strip-label">Actions</p>
            <div className="portal-action-strip">
              {QUICK.map((a) => (
                <ActionNavCard
                  key={a.to + a.label}
                  to={a.to}
                  label={a.label}
                  hint={a.hint}
                />
              ))}
            </div>
          </section>

          <section className="portal-card p-5" data-affordance="static">
            <h2 className="portal-section-title">Role distribution</h2>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {ROLE_ORDER.map((role) => (
                <div
                  key={role}
                  className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
                  data-affordance="static"
                >
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    {ROLE_LABELS[role] || role}
                  </p>
                  <p className="text-xl font-semibold text-au-navy">{by[role] || 0}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="portal-card" data-affordance="static">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div>
                <h2 className="text-xl font-semibold text-au-navy">Recent user-management activity</h2>
                <p className="text-xs text-slate-500">
                  Created, role changes, activation, student links, bulk import
                </p>
              </div>
              <Link to="/app/admin/audit" className="btn-ghost btn-sm">
                View all →
              </Link>
            </div>
            {activity.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500">No administrative audit events yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {activity.map((row) => (
                  <li key={row.id} className="px-4 py-3 text-sm" data-affordance="static">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-au-navy">{row.action}</span>
                      <span className="text-xs text-slate-400">
                        {row.timestamp ? formatDateTime(row.timestamp) : "—"}
                      </span>
                    </div>
                    <p className="mt-1 text-slate-600">{row.description}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Actor: {row.actor_email || (row.user_id ? `user #${row.user_id}` : "system")}
                      {row.entity_id != null ? ` · target #${row.entity_id}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
