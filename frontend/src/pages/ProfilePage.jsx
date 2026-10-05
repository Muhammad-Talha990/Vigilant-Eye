import PageHeader from "../components/PageHeader";
import PageShell from "../components/PageShell";
import { ROLE_LABELS } from "../config/navByRole";
import { useAuth } from "../context/AuthContext";

/**
 * Shared account profile for all portal roles (Google Sign-In explanation).
 */
export default function ProfilePage({ adminBreadcrumb = false }) {
  const { user, logout } = useAuth();
  const role = user?.role || "";
  const breadcrumb = adminBreadcrumb
    ? "Home / Administration / Profile"
    : "Home / Account / Profile";

  return (
    <PageShell narrow>
      <PageHeader
        breadcrumb={breadcrumb}
        title="Profile"
        description="Account information and role-specific settings."
      />

      <dl className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2">
        {[
          ["Display name", user?.name || "—"],
          ["Email", user?.email || "—"],
          ["Portal role", ROLE_LABELS[role] || role || "—"],
          [
            "Account status",
            user?.is_active === false ? "Inactive" : "Active",
          ],
        ].map(([k, v]) => (
          <div
            key={k}
            className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
          >
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {k}
            </dt>
            <dd className="mt-1 break-words text-sm font-medium text-au-navy">
              {v}
            </dd>
          </div>
        ))}
      </dl>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-au-navy">
          Authentication notes
        </h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>
            Password login is disabled for this university deployment. Sign in
            with the Google account matching the authorized portal email.
          </li>
          <li>
            Roles are assigned by an Administrator in VigilantEye. Google does
            not assign portal permissions.
          </li>
          <li>
            Sign-in failures may indicate an inactive or unprovisioned email.
            Contact the Administrator for account status.
          </li>
        </ul>
        <button type="button" className="btn-secondary mt-4" onClick={logout}>
          Sign out
        </button>
      </div>
    </PageShell>
  );
}
