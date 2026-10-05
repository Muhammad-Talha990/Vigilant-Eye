import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import {
  formatResultStatusLabel,
  formatStatusLabel,
} from "../config/casePresentation";
import { RESULT_CONTROL_ROLES } from "../config/roleAccess";
import { formatDateTime } from "../config/dateTime";

import { useAuth } from "../context/AuthContext";
import {
  fetchResultControls,
  releaseResultControl,
} from "../services/api";

const CAN_VIEW = new Set(RESULT_CONTROL_ROLES);
const CAN_RELEASE = new Set(RESULT_CONTROL_ROLES);

function ResultStatusBadge({ status }) {
  const held = status === "HELD";
  const released = status === "RELEASED";
  const label = formatResultStatusLabel(status);
  const style = held
    ? "bg-amber-100 text-amber-950 ring-amber-300"
    : released
      ? "bg-emerald-100 text-emerald-950 ring-emerald-300"
      : "bg-slate-100 text-slate-800 ring-slate-200";
  return (
    <span
      className={`inline-flex items-center rounded-md px-2.5 py-1 text-xs font-bold uppercase tracking-wide ring-1 ring-inset ${style}`}
      title={`Result status: ${label}`}
    >
      {label}
    </span>
  );
}

function Field({ label, children }) {
  if (children == null || children === "" || children === "—") return null;
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-900">{children}</dd>
    </div>
  );
}

function studentPrimary(row) {
  return row.student_name || `Student #${row.student_id}`;
}

function rollPrimary(row) {
  return row.student_roll || "—";
}

function casePrimary(row) {
  return row.case_number || `Case #${row.case_id}`;
}

function programLine(row) {
  return [row.student_program, row.student_department].filter(Boolean).join(" · ");
}

function holdSourceLabel(row) {
  if (row.hold_source === "AUTOMATIC_APPROVE") {
    return `Automatic after UFM case approval (${casePrimary(row)})`;
  }
  if (row.hold_source === "MANUAL") {
    return `Manual result control for ${casePrimary(row)}`;
  }
  return casePrimary(row);
}

export default function ResultControlsPage() {
  const { user } = useAuth();
  const canView = CAN_VIEW.has(user?.role);
  const canRelease = CAN_RELEASE.has(user?.role);

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("HELD");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [confirmHold, setConfirmHold] = useState(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const controls = await fetchResultControls();
      const list = Array.isArray(controls) ? controls : [];
      setItems(list);
      setSelectedId((prev) => {
        if (prev && list.some((r) => r.id === prev)) return prev;
        return list[0]?.id ?? null;
      });
    } catch {
      setError("Unable to load result holds. Please try again.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      setError("Your role cannot view result holds.");
      return;
    }
    load();
  }, [canView]);

  useEffect(() => {
    if (!confirmHold) return undefined;
    function onKey(e) {
      if (e.key === "Escape") setConfirmHold(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirmHold]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return items.filter((r) => {
      if (statusFilter && r.result_status !== statusFilter) return false;
      if (!term) return true;
      const hay = [
        r.student_name,
        r.student_roll,
        r.student_program,
        r.student_department,
        r.case_number,
        String(r.case_id),
        r.reason,
        r.result_status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(term);
    });
  }, [items, statusFilter, query]);

  const selected =
    filtered.find((r) => r.id === selectedId) ||
    filtered[0] ||
    null;

  const heldCount = items.filter((r) => r.result_status === "HELD").length;
  const releasedCount = items.filter((r) => r.result_status === "RELEASED").length;

  async function confirmRelease() {
    if (!confirmHold || !canRelease) return;
    const id = confirmHold.id;
    setMessage("");
    setError("");
    setBusyId(id);
    try {
      const updated = await releaseResultControl(id);
      setMessage(
        `RESULT HOLD RELEASED — ${studentPrimary(confirmHold)} (${rollPrimary(
          confirmHold
        )}) · ${casePrimary(confirmHold)} · Result status: ${formatResultStatusLabel(
          updated?.result_status || "RELEASED"
        )}`
      );
      setConfirmHold(null);
      await load();
    } catch (err) {
      setError(err.message || "Unable to release result hold. Please try again.");
      setConfirmHold(null);
    } finally {
      setBusyId(null);
    }
  }

  if (!canView && !loading) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <p className="font-semibold">Result holds are not available</p>
        <p className="mt-1">
          This administrative view is limited to Exam Department and UFM
          Committee accounts.
        </p>
        <Link
          to="/app/dashboard"
          className="mt-3 inline-flex text-sm font-semibold text-au-blue"
        >
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumb="Home / Result Controls"
        title="Result Controls"
        description="Manage result holds and release controls associated with approved UFM cases."
      />

      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
        <p className="font-semibold text-au-navy">How result holds work</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5">
          <li>
            UFM Committee <strong>Approves</strong> a case → result hold is
            created automatically (On Hold / transcript Blocked).
          </li>
          <li>
            <strong>Return</strong>, <strong>Forward</strong>, and{" "}
            <strong>Reject</strong> do not place or clear a result hold.
          </li>
          <li>
            Exam Department or UFM Committee uses{" "}
            <strong>Release Result Hold</strong> when the restriction may end.
          </li>
        </ol>
        <p className="mt-2 text-xs text-slate-500">
          Manual hold creation is available only via the staff API; the portal
          does not include a place-hold form (approved product scope).
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <label className="block min-w-[16rem] flex-1 text-sm text-slate-600">
          <span className="sr-only">Search student, roll, or case</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search student / roll number / case ID"
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          />
        </label>
        <div
          className="flex flex-wrap gap-2"
          role="group"
          aria-label="Result status filter"
        >
          {[
            { value: "", label: `All (${items.length})` },
            { value: "HELD", label: `On Hold (${heldCount})` },
            { value: "RELEASED", label: `Released (${releasedCount})` },
          ].map((opt) => (
            <button
              key={opt.value || "all"}
              type="button"
              onClick={() => setStatusFilter(opt.value)}
              className={[
                "rounded-lg px-3 py-1.5 text-sm font-semibold ring-1 ring-inset",
                statusFilter === opt.value
                  ? "bg-au-navy text-white ring-au-navy"
                  : "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50",
              ].join(" ")}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <ErrorBanner
          title="Unable to load result holds."
          message={error}
          onRetry={load}
        />
      ) : null}
      {message ? (
        <div
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
        >
          {message}
        </div>
      ) : null}

      {loading ? (
        <LoadingState
          compact
          title="Loading result controls…"
          detail="Retrieving holds linked to UFM cases and students."
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="No result holds currently require action."
          detail="When the UFM Committee approves a case, an On Hold record appears here for the affected student."
          actions={
            <Link to="/app/cases" className="btn-secondary">
              View UFM cases
            </Link>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No matching result controls."
          detail="Try another search or status filter."
          actions={
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setQuery("");
                setStatusFilter("");
              }}
            >
              Clear filters
            </button>
          }
        />
      ) : (
        <div className="portal-split">
          <div className="portal-split-list min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-au-navy">
                Affected students ({filtered.length})
              </h2>
              <p className="text-xs text-slate-500">
                Select a student to see hold detail, source case, and release
                action.
              </p>
            </div>

            <div className="portal-data-cards">
              {filtered.map((r) => {
                const active = selected?.id === r.id;
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setSelectedId(r.id)}
                    className={[
                      "portal-case-card w-full text-left",
                      active ? "ring-2 ring-au-blue" : "",
                    ].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="portal-case-card-title truncate">
                          {studentPrimary(r)}
                        </p>
                        <p className="portal-case-card-meta">
                          Roll {rollPrimary(r)}
                          {programLine(r) ? ` · ${programLine(r)}` : ""}
                        </p>
                      </div>
                      <ResultStatusBadge status={r.result_status} />
                    </div>
                    <p className="portal-case-card-meta mt-2">
                      UFM {casePrimary(r)}
                      {r.case_status
                        ? ` · Case ${formatStatusLabel(r.case_status)}`
                        : ""}
                    </p>
                  </button>
                );
              })}
            </div>

            <div className="portal-table-wrap portal-table-desktop">
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Roll No.</th>
                    <th className="col-hide-md">Program / Dept</th>
                    <th>UFM Case</th>
                    <th className="col-hide-lg">Case Status</th>
                    <th>Result</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => {
                    const active = selected?.id === r.id;
                    return (
                      <tr
                        key={r.id}
                        className={active ? "bg-sky-50/80" : undefined}
                      >
                        <td>
                          <button
                            type="button"
                            onClick={() => setSelectedId(r.id)}
                            className="font-semibold text-au-navy hover:underline"
                          >
                            {studentPrimary(r)}
                          </button>
                        </td>
                        <td className="whitespace-nowrap tabular-nums">
                          {rollPrimary(r)}
                        </td>
                        <td className="col-hide-md text-slate-600">
                          {programLine(r) || "—"}
                        </td>
                        <td>
                          <Link
                            to={`/app/cases/${r.case_id}`}
                            className="font-medium text-au-blue hover:underline"
                          >
                            {casePrimary(r)}
                          </Link>
                        </td>
                        <td className="col-hide-lg">
                          {r.case_status ? (
                            <StatusBadge status={r.case_status} />
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          <ResultStatusBadge status={r.result_status} />
                        </td>
                        <td>
                          <button
                            type="button"
                            onClick={() => setSelectedId(r.id)}
                            className="text-sm font-semibold text-au-blue hover:underline"
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="portal-split-detail portal-card min-w-0 overflow-hidden">
            {selected ? (
              <>
                <div className="portal-panel-header">
                  <h2 className="portal-section-title">Result control</h2>
                  <ResultStatusBadge status={selected.result_status} />
                </div>
                <div className="portal-panel-body space-y-4">
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <Field label="Student">{studentPrimary(selected)}</Field>
                    <Field label="Roll number">{rollPrimary(selected)}</Field>
                    <Field label="Program">{selected.student_program || null}</Field>
                    <Field label="Department">
                      {selected.student_department || null}
                    </Field>
                    <Field label="UFM case">
                      <Link
                        to={`/app/cases/${selected.case_id}`}
                        className="text-au-blue hover:underline"
                      >
                        {casePrimary(selected)}
                      </Link>
                    </Field>
                    <Field label="Case status">
                      {selected.case_status
                        ? formatStatusLabel(selected.case_status)
                        : null}
                    </Field>
                    <Field label="Result status">
                      {formatResultStatusLabel(selected.result_status)}
                    </Field>
                    <Field label="Transcript">
                      {formatStatusLabel(selected.transcript_status)}
                    </Field>
                    <Field label="Hold reason">{selected.reason || null}</Field>
                    <Field label="Source">{holdSourceLabel(selected)}</Field>
                    <Field label="Placed by">
                      {selected.held_by_name ||
                        (selected.held_by != null
                          ? `User #${selected.held_by}`
                          : null)}
                    </Field>
                    <Field label="Placed at">
                      {selected.held_at
                        ? formatDateTime(selected.held_at)
                        : null}
                    </Field>
                    {selected.result_status === "RELEASED" ? (
                      <>
                        <Field label="Released by">
                          {selected.released_by_name ||
                            (selected.released_by != null
                              ? `User #${selected.released_by}`
                              : null)}
                        </Field>
                        <Field label="Released at">
                          {selected.released_at
                            ? formatDateTime(selected.released_at)
                            : null}
                        </Field>
                      </>
                    ) : null}
                  </dl>

                  <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    <p>
                      <strong className="text-slate-800">Case status</strong>{" "}
                      and <strong className="text-slate-800">result status</strong>{" "}
                      are separate. Approving a case places a hold; rejecting or
                      returning a case does not change an existing result
                      control by itself.
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Link
                      to={`/app/cases/${selected.case_id}`}
                      className="btn-secondary btn-sm"
                    >
                      Open UFM case
                    </Link>
                    <Link to="/app/audit" className="btn-ghost btn-sm">
                      Audit history
                    </Link>
                    {selected.result_status === "HELD" && canRelease ? (
                      <button
                        type="button"
                        disabled={busyId === selected.id}
                        onClick={() => setConfirmHold(selected)}
                        className="btn-danger btn-sm"
                      >
                        {busyId === selected.id
                          ? "…"
                          : "Release Result Hold"}
                      </button>
                    ) : null}
                    {selected.result_status === "RELEASED" ? (
                      <span className="self-center text-xs font-medium text-slate-500">
                        Hold already released
                      </span>
                    ) : null}
                  </div>
                </div>
              </>
            ) : (
              <div className="px-5 py-8 text-sm text-slate-500">
                Select a student hold to view details.
              </div>
            )}
          </aside>
        </div>
      )}

      {confirmHold ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="release-hold-title"
            className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
          >
            <h3
              id="release-hold-title"
              className="text-lg font-semibold text-au-navy"
            >
              Release result hold for this student?
            </h3>
            <dl className="mt-3 space-y-2 text-sm text-slate-700">
              <div>
                <span className="text-slate-400">Student: </span>
                <span className="font-semibold">{studentPrimary(confirmHold)}</span>
              </div>
              <div>
                <span className="text-slate-400">Roll number: </span>
                <span className="font-semibold">{rollPrimary(confirmHold)}</span>
              </div>
              <div>
                <span className="text-slate-400">UFM case: </span>
                <span className="font-semibold">{casePrimary(confirmHold)}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-slate-400">Current status: </span>
                <ResultStatusBadge status={confirmHold.result_status} />
              </div>
            </dl>
            <p className="mt-3 text-sm text-slate-600">
              This sets result status to Released and transcript to Allowed.
              Name and timestamp are recorded for audit.
            </p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                disabled={busyId === confirmHold.id}
                onClick={() => setConfirmHold(null)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busyId === confirmHold.id}
                onClick={confirmRelease}
                className="btn-danger"
              >
                {busyId === confirmHold.id ? "Releasing…" : "Release Hold"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
