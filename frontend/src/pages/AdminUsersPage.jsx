import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { ROLE_LABELS } from "../config/navByRole";
import { formatDate } from "../config/dateTime";

import { useAuth } from "../context/AuthContext";
import {
  activateAdminUser,
  createAdminUser,
  deactivateAdminUser,
  fetchAdminUserStats,
  fetchAdminUsers,
  patchAdminUser,
} from "../services/api";

const ALL_ROLES = [
  "ADMINISTRATOR",
  "STUDENT",
  "INVIGILATOR",
  "HOD",
  "DEC",
  "EXAM_DEPARTMENT",
  "UFM_COMMITTEE",
];

const ROLE_BADGE = {
  ADMINISTRATOR: "bg-violet-50 text-violet-900",
  STUDENT: "bg-sky-50 text-sky-900",
  INVIGILATOR: "bg-indigo-50 text-indigo-900",
  HOD: "bg-amber-50 text-amber-950",
  DEC: "bg-orange-50 text-orange-900",
  EXAM_DEPARTMENT: "bg-teal-50 text-teal-900",
  UFM_COMMITTEE: "bg-rose-50 text-rose-900",
};

function RoleBadge({ role }) {
  return (
    <span
      className={`inline-flex rounded px-2 py-0.5 text-xs font-semibold ${
        ROLE_BADGE[role] || "bg-slate-100 text-slate-700"
      }`}
    >
      {ROLE_LABELS[role] || role}
    </span>
  );
}

function ConfirmDialog({ open, title, body, confirmLabel, onConfirm, onCancel, busy }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
      >
        <h3 className="text-lg font-semibold text-au-navy">{title}</h3>
        <p className="mt-2 text-sm text-slate-600">{body}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-lg bg-au-navy px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminUsersPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMINISTRATOR";
  const [searchParams, setSearchParams] = useSearchParams();

  const [stats, setStats] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [kind, setKind] = useState("");
  const [linked, setLinked] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [form, setForm] = useState({
    email: "",
    name: "",
    role: "STUDENT",
    student_roll: "",
    is_active: true,
  });

  function clearFilters() {
    setQ("");
    setRole("");
    setActiveFilter("");
    setKind("");
    setLinked("");
    setPage(1);
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {
        page,
        page_size: pageSize,
        q: q.trim() || undefined,
        role: role || undefined,
        kind: kind || undefined,
        linked: linked || undefined,
      };
      if (activeFilter === "1") params.is_active = true;
      if (activeFilter === "0") params.is_active = false;
      const [list, st] = await Promise.all([
        fetchAdminUsers(params),
        fetchAdminUserStats(),
      ]);
      setItems(list.items || []);
      setTotal(list.total || 0);
      setStats(st);
    } catch (err) {
      setError(err.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, q, role, activeFilter, kind, linked]);

  useEffect(() => {
    if (isAdmin) load();
    else setLoading(false);
  }, [isAdmin, load]);

  useEffect(() => {
    if (searchParams.get("create") === "1") {
      setCreateOpen(true);
      searchParams.delete("create");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  async function runConfirmed() {
    if (!confirm) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await confirm.action();
      setMessage(confirm.success || "Updated.");
      setConfirm(null);
      setEditUser(null);
      await load();
    } catch (err) {
      setError(err.message || "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const payload = {
        email: form.email.trim(),
        role: form.role,
        name: form.name.trim() || undefined,
        student_roll:
          form.role === "STUDENT" ? form.student_roll.trim() || undefined : undefined,
        is_active: Boolean(form.is_active),
      };
      const created = await createAdminUser(payload);
      setMessage(`Created ${created.email} as ${created.role}.`);
      setCreateOpen(false);
      setForm({
        email: "",
        name: "",
        role: "STUDENT",
        student_roll: "",
        is_active: true,
      });
      await load();
    } catch (err) {
      setError(err.message || "Create failed");
    } finally {
      setBusy(false);
    }
  }

  if (!isAdmin) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Administrator user management is restricted to the ADMINISTRATOR role.
      </div>
    );
  }

  const inputClass =
    "w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm";
  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Administration / Users"
        title="Portal Users"
        description="Authorize portal accounts and assign institutional roles."
      />

      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}

      {stats ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Total", stats.total],
            ["Active", stats.active],
            ["Inactive", stats.inactive],
            ["Students", stats.by_role?.STUDENT ?? 0],
            ["Admins", stats.by_role?.ADMINISTRATOR ?? 0],
          ].map(([label, value]) => (
            <div
              key={label}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {label}
              </p>
              <p className="mt-1 text-2xl font-semibold text-au-navy">{value}</p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="min-w-[12rem] flex-1 text-sm">
          <span className="mb-1 block text-slate-600">Search</span>
          <input
            className={inputClass}
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
            placeholder="Email, name, roll, user id"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Role</span>
          <select
            className={inputClass}
            value={role}
            onChange={(e) => {
              setPage(1);
              setRole(e.target.value);
            }}
          >
            <option value="">All</option>
            {ALL_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r] || r}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Status</span>
          <select
            className={inputClass}
            value={activeFilter}
            onChange={(e) => {
              setPage(1);
              setActiveFilter(e.target.value);
            }}
          >
            <option value="">All</option>
            <option value="1">Active</option>
            <option value="0">Inactive</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Kind</span>
          <select
            className={inputClass}
            value={kind}
            onChange={(e) => {
              setPage(1);
              setKind(e.target.value);
            }}
          >
            <option value="">All</option>
            <option value="student">Students</option>
            <option value="staff">Staff / Admin</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Student link</span>
          <select
            className={inputClass}
            value={linked}
            onChange={(e) => {
              setPage(1);
              setLinked(e.target.value);
            }}
          >
            <option value="">Any</option>
            <option value="linked">Linked</option>
            <option value="unlinked">Unlinked</option>
          </select>
        </label>
        <button
          type="button"
          className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700"
          onClick={clearFilters}
        >
          Clear filters
        </button>
        <button
          type="button"
          className="rounded-lg bg-au-navy px-4 py-2.5 text-sm font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-au-navy"
          onClick={() => setCreateOpen(true)}
        >
          + Add User
        </button>
        <Link
          to="/app/admin/import"
          className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-au-navy"
        >
          Import CSV
        </Link>
      </div>

      {loading ? (
        <LoadingState label="Loading users…" />
      ) : (
        <>
          <div className="portal-data-cards rounded-xl border border-slate-200 bg-white shadow-sm">
            {items.length === 0 ? (
              <p className="px-4 py-8 text-center text-slate-500">
                No users match the current filters.
              </p>
            ) : (
              items.map((u) => (
                <div key={u.id} className="portal-case-card" data-affordance="static">
                  <div className="flex items-start justify-between gap-2">
                    <p className="portal-case-card-title">{u.name}</p>
                    {u.is_active ? (
                      <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                        Active
                      </span>
                    ) : (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                        Inactive
                      </span>
                    )}
                  </div>
                  <p className="portal-case-card-meta cell-wrap">{u.email}</p>
                  <p className="portal-case-card-meta">
                    <RoleBadge role={u.role} />
                    {u.student_roll ? ` · ${u.student_roll}` : ""}
                  </p>
                  <div className="mt-3">
                    <button
                      type="button"
                      className="portal-text-link"
                      onClick={() =>
                        setEditUser({
                          ...u,
                          newRole: u.role,
                          newName: u.name,
                          newRoll: u.student_roll || "",
                        })
                      }
                    >
                      Edit
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="portal-table-wrap portal-table-desktop">
              <table className="portal-table">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="px-4 py-3 col-hide-md">Student link</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 col-hide-lg">Created</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-4 py-8 text-center text-slate-500"
                      >
                        No users match the current filters.
                      </td>
                    </tr>
                  ) : (
                    items.map((u) => (
                      <tr key={u.id} className="border-b border-slate-100">
                        <td className="px-4 py-3 font-medium text-au-navy">
                          {u.name}
                        </td>
                        <td className="px-4 py-3 cell-wrap text-slate-700">
                          {u.email}
                        </td>
                        <td className="px-4 py-3">
                          <RoleBadge role={u.role} />
                        </td>
                        <td className="px-4 py-3 col-hide-md">
                          {u.student_roll || "—"}
                        </td>
                        <td className="px-4 py-3">
                          {u.is_active ? (
                            <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                              Active
                            </span>
                          ) : (
                            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                              Inactive
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 col-hide-lg text-slate-500">
                          {u.created_at
                            ? formatDate(u.created_at)
                            : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            className="portal-text-link"
                            onClick={() =>
                              setEditUser({
                                ...u,
                                newRole: u.role,
                                newName: u.name,
                                newRoll: u.student_roll || "",
                              })
                            }
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3 text-sm text-slate-600">
              <span>
                {total} user{total === 1 ? "" : "s"} · page {page} of {pages}
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
      )}

      {createOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4">
          <form
            onSubmit={onCreate}
            className="w-full max-w-xl space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
          >
            <h3 className="text-lg font-semibold text-au-navy">Add User</h3>
            <div className="max-h-40 overflow-y-auto rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-sm text-sky-950">
              <p className="font-semibold">Google account onboarding</p>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-xs leading-relaxed">
                <li>Enter the user’s exact Google email.</li>
                <li>Assign the VigilantEye portal role.</li>
                <li>Save — the email becomes an authorized portal account.</li>
                <li>No portal password is created or emailed.</li>
                <li>The user opens the portal login page.</li>
                <li>They click <strong>Continue with Google</strong>.</li>
                <li>They must sign in with that exact Google email.</li>
                <li>The portal finds the matching User record.</li>
                <li>Access follows the database role (not Google claims).</li>
                <li>They land on the dashboard for that role.</li>
              </ol>
            </div>
            <label className="block text-sm">
              Name
              <input
                className={`${inputClass} mt-1`}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </label>
            <label className="block text-sm">
              Email
              <input
                required
                type="email"
                className={`${inputClass} mt-1`}
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </label>
            <label className="block text-sm">
              Role
              <select
                required
                className={`${inputClass} mt-1`}
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              >
                {ALL_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r] || r}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) =>
                  setForm((f) => ({ ...f, is_active: e.target.checked }))
                }
              />
              Active (unchecked creates an inactive account that cannot sign in)
            </label>
            {form.role === "STUDENT" ? (
              <label className="block text-sm">
                Student roll (link existing or create student record)
                <input
                  required
                  className={`${inputClass} mt-1`}
                  value={form.student_roll}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, student_roll: e.target.value }))
                  }
                />
              </label>
            ) : (
              <p className="text-xs text-slate-500">
                Staff roles do not require a student record link.
              </p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                onClick={() => setCreateOpen(false)}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg bg-au-navy px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {busy ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {editUser ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-lg space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-lg">
            <h3 className="text-lg font-semibold text-au-navy">Edit user</h3>
            <label className="block text-sm">
              Email (read-only)
              <input
                className={`${inputClass} mt-1 bg-slate-100`}
                value={editUser.email}
                readOnly
                disabled
              />
            </label>
            <p className="text-xs text-slate-500">
              Email is the Google identity and cannot be edited here. To change
              it, create/link the correct account.
            </p>
            <label className="block text-sm">
              Name
              <input
                className={`${inputClass} mt-1`}
                value={editUser.newName}
                onChange={(e) =>
                  setEditUser((u) => ({ ...u, newName: e.target.value }))
                }
              />
            </label>
            <label className="block text-sm">
              Role
              <select
                className={`${inputClass} mt-1`}
                value={editUser.newRole}
                onChange={(e) =>
                  setEditUser((u) => ({ ...u, newRole: e.target.value }))
                }
              >
                {ALL_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r] || r}
                  </option>
                ))}
              </select>
            </label>
            {editUser.newRole === "STUDENT" ? (
              <label className="block text-sm">
                Student roll
                <input
                  className={`${inputClass} mt-1`}
                  value={editUser.newRoll}
                  onChange={(e) =>
                    setEditUser((u) => ({ ...u, newRoll: e.target.value }))
                  }
                />
              </label>
            ) : null}
            <div className="flex flex-wrap gap-2 pt-2">
              <button
                type="button"
                className="rounded-lg bg-au-navy px-3 py-2 text-sm font-semibold text-white"
                onClick={() => {
                  const roleChanging = editUser.newRole !== editUser.role;
                  setConfirm({
                    title: roleChanging ? "Change role?" : "Save user changes?",
                    body: roleChanging
                      ? `Change role for ${editUser.email} from ${editUser.role} to ${editUser.newRole}?`
                      : `Update account details for ${editUser.email}.`,
                    confirmLabel: roleChanging ? "Change role" : "Save changes",
                    success: roleChanging ? "Role updated." : "User updated.",
                    action: async () => {
                      const payload = { name: editUser.newName.trim() };
                      if (roleChanging) {
                        payload.role = editUser.newRole;
                      }
                      if (editUser.newRole === "STUDENT") {
                        payload.student_roll = editUser.newRoll.trim();
                      } else if (editUser.student_roll) {
                        payload.unlink_student = true;
                      }
                      await patchAdminUser(editUser.id, payload);
                    },
                  });
                }}
              >
                Save
              </button>
              {editUser.is_active ? (
                <button
                  type="button"
                  className="rounded-lg border border-red-300 px-3 py-2 text-sm font-semibold text-red-700"
                  onClick={() =>
                    setConfirm({
                      title: "Deactivate account?",
                      body: `Deactivate this account? The user will no longer be able to access VigilantEye. (${editUser.email})`,
                      confirmLabel: "Deactivate",
                      success: "User deactivated.",
                      action: () => deactivateAdminUser(editUser.id),
                    })
                  }
                >
                  Deactivate
                </button>
              ) : (
                <button
                  type="button"
                  className="rounded-lg border border-emerald-300 px-3 py-2 text-sm font-semibold text-emerald-800"
                  onClick={() =>
                    setConfirm({
                      title: "Reactivate user?",
                      body: `${editUser.email} will be allowed to sign in again.`,
                      confirmLabel: "Reactivate",
                      success: "User reactivated.",
                      action: () => activateAdminUser(editUser.id),
                    })
                  }
                >
                  Reactivate
                </button>
              )}
              {editUser.student_roll ? (
                <button
                  type="button"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  onClick={() =>
                    setConfirm({
                      title: "Unlink student?",
                      body: `Remove student roll ${editUser.student_roll} from ${editUser.email}.`,
                      confirmLabel: "Unlink",
                      success: "Student unlinked.",
                      action: () =>
                        patchAdminUser(editUser.id, { unlink_student: true }),
                    })
                  }
                >
                  Unlink student
                </button>
              ) : null}
              <button
                type="button"
                className="ml-auto rounded-lg border border-slate-300 px-3 py-2 text-sm"
                onClick={() => setEditUser(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title}
        body={confirm?.body}
        confirmLabel={confirm?.confirmLabel}
        onConfirm={runConfirmed}
        onCancel={() => setConfirm(null)}
        busy={busy}
      />
    </div>
  );
}
