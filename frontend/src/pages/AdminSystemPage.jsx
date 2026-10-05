import { useCallback, useEffect, useState } from "react";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { fetchAdminSystemInfo, sendAdminTestEmail } from "../services/api";

export default function AdminSystemPage() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [testBusy, setTestBusy] = useState(false);
  const [testMsg, setTestMsg] = useState("");
  const [testErr, setTestErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminSystemInfo();
      setInfo(data);
    } catch (err) {
      setError(err.message || "Failed to load system info");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchAdminSystemInfo();
        if (!cancelled) setInfo(data);
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load system info");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSendTestEmail() {
    setTestBusy(true);
    setTestMsg("");
    setTestErr("");
    try {
      const res = await sendAdminTestEmail();
      setTestMsg(
        res.ok
          ? `${res.detail} (result=${res.result}, to=${res.to_masked})`
          : `${res.detail} (result=${res.result}, to=${res.to_masked})`
      );
      await load();
    } catch (err) {
      setTestErr(err.message || "Test email failed");
    } finally {
      setTestBusy(false);
    }
  }

  const emailLabel = (() => {
    if (!info) return "—";
    if (info.email_notifications === "disabled") return "Disabled";
    if (info.email_notifications === "mock") return "Enabled (MOCK — SMTP incomplete)";
    if (info.email_notifications === "enabled") return "Enabled";
    return info.email_enabled ? "Enabled" : "Disabled";
  })();

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Administration / System"
        title="System Information"
        description="Runtime configuration flags. Credentials and secrets are not displayed."
      />
      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {loading ? <LoadingState label="Loading…" /> : null}
      {info ? (
        <>
          <div
            className={`rounded-xl border px-4 py-3 text-sm ${
              info.is_production
                ? "border-amber-200 bg-amber-50 text-amber-950"
                : "border-emerald-200 bg-emerald-50 text-emerald-950"
            }`}
          >
            Environment: <strong>{info.app_env}</strong> —{" "}
            {info.is_production ? "Production posture" : "Development / non-production"}
          </div>
          <dl className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2">
            {[
              ["Project", info.project],
              ["Application version", info.application_version || "—"],
              ["Authentication mode", info.auth_mode],
              ["Google authentication", info.google_auth_enabled ? "enabled" : "disabled"],
              ["Password login", info.password_login_enabled ? "enabled" : "disabled"],
              ["Demo seed / helpers", info.demo_helpers_enabled ? "enabled" : "disabled"],
              ["API available", info.api_available === false ? "no" : "yes"],
              ["Database available", info.database_available === false ? "no" : "yes"],
              ["DB migration (current)", info.alembic_current_revision || "—"],
              ["DB migration (head)", info.alembic_head_revision || "—"],
              [
                "Migrations pending",
                info.migrations_pending == null
                  ? "—"
                  : info.migrations_pending
                    ? "yes"
                    : "no",
              ],
              ["Portal roles", (info.portal_roles || []).join(", ")],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{k}</dt>
                <dd className="mt-1 text-sm font-medium text-au-navy break-words">{v}</dd>
              </div>
            ))}
          </dl>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
            <div>
              <h2 className="text-base font-semibold text-au-navy">Email notifications</h2>
              <p className="mt-1 text-sm text-slate-600">
                Google Sign-In identifies users. SMTP delivers notifications to each user&apos;s{" "}
                <code className="text-xs">User.email</code>. They are separate systems.
              </p>
            </div>
            <dl className="grid gap-3 sm:grid-cols-2">
              {[
                ["Email notifications", emailLabel],
                ["SMTP", info.smtp_configured ? "Configured" : "Not configured"],
                ["Provider / host", info.smtp_host || "—"],
                ["SMTP port", info.smtp_port != null ? String(info.smtp_port) : "—"],
                ["TLS", info.smtp_use_tls == null ? "—" : info.smtp_use_tls ? "yes" : "no"],
                ["From address set", info.smtp_from_configured ? "yes" : "no"],
                ["SMTP auth set", info.smtp_auth_configured ? "yes" : "no"],
                ["Portal base URL set", info.portal_base_url_configured ? "yes" : "no"],
                ["Last delivery", info.last_delivery_status || "never"],
                ["Last delivery at", info.last_delivery_at || "—"],
                ["Last recipient (masked)", info.last_delivery_to_masked || "—"],
                ["Last error category", info.last_delivery_error_category || "—"],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{k}</dt>
                  <dd className="mt-1 text-sm font-medium text-au-navy break-words">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                type="button"
                disabled={testBusy}
                onClick={onSendTestEmail}
                className="rounded-lg bg-au-navy px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {testBusy ? "Sending…" : "Send Test Email"}
              </button>
              <span className="text-xs text-slate-500">
                Sends only to the signed-in Administrator User.email (no arbitrary recipients).
              </span>
            </div>
            {testMsg ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                {testMsg}
              </div>
            ) : null}
            {testErr ? (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {testErr}
              </div>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
