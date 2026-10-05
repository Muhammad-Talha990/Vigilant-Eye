import { useEffect, useMemo, useState } from "react";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { DEMO_FORM_PASSWORD } from "../config/demoMode";
import { ROLE_LABELS } from "../config/navByRole";
import { formatDateTime } from "../config/dateTime";

import { useAuth } from "../context/AuthContext";
import { createUser, fetchUsers } from "../services/api";

const STAFF_ROLES = [
  "INVIGILATOR",
  "HOD",
  "DEC",
  "EXAM_DEPARTMENT",
  "UFM_COMMITTEE",
];

const CAN_CREATE_STAFF = new Set(["HOD", "EXAM_DEPARTMENT"]);
const CAN_VIEW = new Set(["HOD", "EXAM_DEPARTMENT", "UFM_COMMITTEE"]);

export default function UsersPage() {
  const { user } = useAuth();
  const canView = CAN_VIEW.has(user?.role);
  const canCreate = CAN_CREATE_STAFF.has(user?.role);

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [roleFilter, setRoleFilter] = useState("");
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: DEMO_FORM_PASSWORD,
    role: "INVIGILATOR",
  });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchUsers(null, { staffOnly: true });
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Failed to load staff users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (canView) load();
    else setLoading(false);
  }, [canView]);

  const filtered = useMemo(() => {
    if (!roleFilter) return items;
    return items.filter((u) => u.role === roleFilter);
  }, [items, roleFilter]);

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const created = await createUser({
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        role: form.role,
      });
      setMessage(`Created ${created.email} as ${created.role}.`);
      setForm((prev) => ({
        ...prev,
        name: "",
        email: "",
        password: DEMO_FORM_PASSWORD,
      }));
      await load();
    } catch (err) {
      setError(err.message || "Create user failed");
    } finally {
      setBusy(false);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm";

  if (!canView) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Staff user management is restricted to HOD, Exam Department, and UFM
        Committee.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / User Management"
        title="User Management"
        description="Portal accounts for invigilators and institutional reviewers."
      />

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}

      {canCreate ? (
        <form
          onSubmit={onSubmit}
          className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2"
        >
          <h2 className="font-semibold text-au-navy sm:col-span-2">
            Register Staff User
          </h2>
          <input
            required
            className={inputClass}
            placeholder="Full name"
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
          />
          <input
            required
            type="email"
            className={inputClass}
            placeholder="Email"
            value={form.email}
            onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
          />
          <select
            required
            className={inputClass}
            value={form.role}
            onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))}
          >
            {STAFF_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r] || r}
              </option>
            ))}
          </select>
          <input
            required
            type="password"
            minLength={4}
            className={inputClass}
            placeholder="Initial password"
            value={form.password}
            onChange={(e) =>
              setForm((p) => ({ ...p, password: e.target.value }))
            }
          />
          <button
            type="submit"
            disabled={busy}
            className="btn-primary sm:col-span-2 sm:w-fit"
          >
            {busy ? "Creating…" : "Create Staff User"}
          </button>
        </form>
      ) : (
        <p className="text-sm text-slate-500">
          View-only for UFM Committee. HOD / Exam Department can create accounts.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Filter role
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">All staff</option>
            {STAFF_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r] || r}
              </option>
            ))}
          </select>
        </label>
        <span className="text-sm text-slate-500">{filtered.length} users</span>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <LoadingState
            compact
            title="Loading staff users…"
            detail="Retrieving portal accounts."
          />
        ) : (
          <div className="portal-table-wrap">
            <table className="portal-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Active</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td className="text-slate-500" colSpan={6}>
                      No staff users match this filter.
                    </td>
                  </tr>
                ) : (
                  filtered.map((u) => (
                    <tr key={u.id}>
                      <td>{u.id}</td>
                      <td className="font-medium text-au-navy">{u.name}</td>
                      <td>{u.email}</td>
                      <td>{ROLE_LABELS[u.role] || u.role}</td>
                      <td>{u.is_active ? "Yes" : "No"}</td>
                      <td className="text-slate-500">
                        {u.created_at
                          ? formatDateTime(u.created_at)
                          : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
