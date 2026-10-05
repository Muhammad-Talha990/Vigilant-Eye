import { useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { useAuth } from "../context/AuthContext";
import {
  confirmAdminUserImport,
  previewAdminUserImport,
} from "../services/api";

function RowTable({ title, rows, tone }) {
  if (!rows?.length) return null;
  const border =
    tone === "bad"
      ? "border-red-200"
      : tone === "warn"
        ? "border-amber-200"
        : "border-emerald-200";
  return (
    <section className={`rounded-xl border ${border} bg-white shadow-sm`}>
      <div className="border-b border-slate-100 px-4 py-3">
        <h3 className="font-semibold text-au-navy">
          {title} ({rows.length})
        </h3>
      </div>
      <div className="portal-table-wrap">
        <table className="portal-table">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Row</th>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Roll</th>
              <th className="px-3 py-2">Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.row_number}-${r.email}-${r.detail}`} className="border-t border-slate-100">
                <td className="px-3 py-2">{r.row_number}</td>
                <td className="px-3 py-2">{r.email}</td>
                <td className="px-3 py-2">{r.role}</td>
                <td className="px-3 py-2">{r.name || "—"}</td>
                <td className="px-3 py-2">{r.student_roll || "—"}</td>
                <td className="px-3 py-2 text-slate-600">{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function AdminImportPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMINISTRATOR";
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  if (!isAdmin) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Bulk import is restricted to the ADMINISTRATOR role.
      </div>
    );
  }

  async function onPreview(e) {
    e.preventDefault();
    if (!file) {
      setError("Choose a CSV file first.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const data = await previewAdminUserImport(file);
      setPreview(data);
    } catch (err) {
      setPreview(null);
      setError(err.message || "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function onImport() {
    if (!preview?.valid?.length) return;
    setBusy(true);
    setError("");
    try {
      const data = await confirmAdminUserImport(preview.valid);
      setResult(data);
      setConfirmOpen(false);
      setPreview(null);
      setFile(null);
    } catch (err) {
      setError(err.message || "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Administration / Import"
        title="Bulk User Import"
        description="Import portal users from CSV with validation and confirmation."
      />

      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
        <p className="font-semibold text-au-navy">CSV columns</p>
        <p className="mt-1 font-mono text-xs">email,role,name,student_roll</p>
        <p className="mt-2">
          STUDENT rows require <code>student_roll</code>. Staff rows must leave
          roll empty. Supported roles: ADMINISTRATOR, STUDENT, INVIGILATOR, HOD,
          DEC, EXAM_DEPARTMENT, UFM_COMMITTEE.
        </p>
        <p className="mt-2 rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-sky-950">
          Imported accounts sign in with the authorized Google account associated
          with each email. No portal passwords are created.
        </p>
        <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs text-slate-500">
          <li>Upload CSV</li>
          <li>Preview classification (valid / invalid / duplicates / conflicts)</li>
          <li>Confirm import explicitly</li>
          <li>Review created / skipped / conflicts summary</li>
        </ol>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              const sample =
                "email,role,name,student_roll\n" +
                "invigilator.example@gmail.com,INVIGILATOR,Example Invigilator,\n" +
                "hod.example@gmail.com,HOD,Example HOD,\n" +
                "student.example@students.au.edu.pk,STUDENT,Example Student,ROLL001\n";
              const blob = new Blob([sample], { type: "text/csv;charset=utf-8" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "vigilanteye_users_sample.csv";
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Download sample CSV
          </button>
          <a
            href="/samples/vigilanteye_users_sample.csv"
            className="portal-text-link"
            download="vigilanteye_users_sample.csv"
          >
            Open sample CSV file
          </a>
          <Link to="/app/admin/users" className="portal-text-link">
            ← Back to users
          </Link>
        </div>
      </div>

      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <p className="font-semibold">Import result summary</p>
          <ul className="mt-2 list-disc pl-5">
            <li>Created: {result.created}</li>
            <li>Already existing (skipped): {result.already_existing}</li>
            <li>Conflicts: {result.conflicts}</li>
            <li>Invalid: {result.invalid}</li>
            <li>Rejected: {result.rejected}</li>
          </ul>
          {result.errors?.length ? (
            <div className="mt-3">
              <p className="font-semibold">Error details</p>
              <ul className="mt-1 list-disc pl-5">
                {result.errors.map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <form
        onSubmit={onPreview}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="min-w-[14rem] flex-1 text-sm">
          <span className="mb-1 block text-slate-600">CSV file</span>
          <label className="btn-secondary inline-flex w-full max-w-md cursor-pointer justify-start gap-2 overflow-hidden">
            <input
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                setPreview(null);
                setResult(null);
              }}
            />
            <span className="shrink-0 rounded bg-sky-100 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-au-navy">
              Choose file
            </span>
            <span className="truncate font-medium text-slate-700">
              {file ? file.name : "No file chosen — click to browse"}
            </span>
          </label>
        </div>
        <button
          type="submit"
          disabled={busy || !file}
          className="btn-primary"
        >
          {busy ? "Parsing…" : "Preview import"}
        </button>
      </form>

      {preview ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
            Total rows: {preview.total_rows}. Ready to create:{" "}
            <strong>{preview.can_import_count}</strong>. Role conflicts and
            student-link problems are never silently applied.
          </div>
          <RowTable title="Valid" rows={preview.valid} tone="ok" />
          <RowTable title="Already exists" rows={preview.already_exists} tone="warn" />
          <RowTable
            title="Role conflict"
            rows={preview.role_conflicts?.length ? preview.role_conflicts : preview.conflicts?.filter((r) => !String(r.detail || "").includes("already linked"))}
            tone="warn"
          />
          <RowTable
            title="Student link problem"
            rows={
              preview.student_link_problems?.length
                ? preview.student_link_problems
                : preview.conflicts?.filter((r) =>
                    String(r.detail || "").includes("already linked")
                  )
            }
            tone="warn"
          />
          <RowTable title="Duplicate" rows={preview.duplicates} tone="bad" />
          <RowTable title="Invalid" rows={preview.invalid} tone="bad" />
          <button
            type="button"
            disabled={!preview.can_import_count || busy}
            className="btn-success"
            onClick={() => setConfirmOpen(true)}
          >
            Confirm import of {preview.can_import_count} user
            {preview.can_import_count === 1 ? "" : "s"}
          </button>
        </div>
      ) : null}

      {confirmOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
          >
            <h3 className="text-lg font-semibold text-au-navy">Confirm bulk import?</h3>
            <p className="mt-2 text-sm text-slate-600">
              This will create {preview?.can_import_count || 0} new authorized
              portal users. Existing accounts and role conflicts will not be
              changed.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setConfirmOpen(false)}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-success"
                onClick={onImport}
                disabled={busy}
              >
                {busy ? "Importing…" : "Import now"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
