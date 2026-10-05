import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { formatViolationLabel } from "../config/casePresentation";
import { formatDateTime } from "../config/dateTime";

import {
  CASE_CREATE_ROLES,
  DETECTION_ROLES,
  roleIn,
} from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";
import {
  createDraftCaseFromDetection,
  fetchDetections,
  fetchExams,
  fetchStudents,
  markAllDetectionsSeen,
  markDetectionSeen,
} from "../services/api";

/** C26-FIX: detections and case creation are Invigilator-only. */
export default function DetectionsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canView = roleIn(user?.role, DETECTION_ROLES);
  const canCreateCase = roleIn(user?.role, CASE_CREATE_ROLES);
  const { refreshDetectionsBadge } = useOutletContext() || {};
  const [items, setItems] = useState([]);
  const [students, setStudents] = useState([]);
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draftFor, setDraftFor] = useState(null);
  const [studentId, setStudentId] = useState("");
  const [examId, setExamId] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftError, setDraftError] = useState("");
  const [filter, setFilter] = useState("all"); // all | new

  const unseenCount = useMemo(
    () => items.filter((d) => !d.is_seen).length,
    [items]
  );

  const visible = useMemo(() => {
    if (filter === "new") return items.filter((d) => !d.is_seen);
    return items;
  }, [items, filter]);

  async function load({ silent = false } = {}) {
    if (!canView) return;
    if (!silent) {
      setLoading(true);
      setError("");
    }
    try {
      const [data, s, e] = await Promise.all([
        fetchDetections(true),
        silent ? Promise.resolve(null) : fetchStudents().catch(() => []),
        silent ? Promise.resolve(null) : fetchExams().catch(() => []),
      ]);
      setItems(Array.isArray(data) ? data : []);
      if (!silent) {
        setStudents(Array.isArray(s) ? s : []);
        setExams(Array.isArray(e) ? e : []);
        const demo = (s || []).find((st) => st.student_id === "DEMO001");
        setStudentId(
          demo ? String(demo.id) : s?.[0]?.id ? String(s[0].id) : ""
        );
        setExamId(e?.[0]?.id ? String(e[0].id) : "");
      }
      if (refreshDetectionsBadge) await refreshDetectionsBadge();
    } catch {
      if (!silent) setError("Unable to load detections. Please try again.");
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      return undefined;
    }
    load();
    const timer = setInterval(() => load({ silent: true }), 4000);
    const onFocus = () => load({ silent: true });
    const onVisible = () => {
      if (document.visibilityState === "visible") onFocus();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView]);

  useEffect(() => {
    if (!draftFor) return undefined;
    function onKey(e) {
      if (e.key === "Escape") setDraftFor(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [draftFor]);

  async function refreshBadge() {
    if (refreshDetectionsBadge) await refreshDetectionsBadge();
  }

  async function onMarkSeen(id) {
    try {
      await markDetectionSeen(id);
      setItems((prev) =>
        prev.map((d) => (d.id === id ? { ...d, is_seen: true } : d))
      );
      await refreshBadge();
    } catch {
      setError("Unable to mark detection as seen. Please try again.");
    }
  }

  async function onMarkAllSeen() {
    try {
      await markAllDetectionsSeen();
      setItems((prev) => prev.map((d) => ({ ...d, is_seen: true })));
      await refreshBadge();
    } catch {
      setError("Unable to mark all detections as seen. Please try again.");
    }
  }

  async function openDraft(d) {
    if (!d.is_seen) await onMarkSeen(d.id);
    setDraftFor(d);
  }

  async function submitDraft() {
    if (!draftFor) return;
    setDraftError("");
    setBusy(true);
    try {
      if (!draftFor.is_seen) await onMarkSeen(draftFor.id);
      const caseRow = await createDraftCaseFromDetection(draftFor.id, {
        student_id: Number(studentId),
        exam_id: Number(examId),
      });
      setDraftFor(null);
      navigate(`/app/cases/${caseRow.id}`);
    } catch (err) {
      setDraftError(err.message || "Could not create draft case");
    } finally {
      setBusy(false);
    }
  }

  if (!canView) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <p className="font-semibold">Detections are not available</p>
        <p className="mt-1">
          Detection alerts are limited to invigilators and authorized monitoring
          staff. This screen is not part of the student portal.
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
        breadcrumb="Home / Detections & Alerts"
        title="Detections and Alerts"
        description={
          unseenCount > 0
            ? `Confirmed AI-assisted detection alerts from examination monitoring · ${unseenCount} unseen.`
            : "Confirmed AI-assisted detection alerts from examination monitoring."
        }
        actions={
          <>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              aria-label="Filter detections"
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="all">All alerts</option>
              <option value="new">Unseen only</option>
            </select>
            <button
              type="button"
              disabled={unseenCount === 0}
              onClick={onMarkAllSeen}
              className="btn-secondary"
            >
              Mark all seen
            </button>
            {canCreateCase ? (
              <>
                <Link to="/app/monitoring" className="btn-secondary">
                  Live Monitoring
                </Link>
                <Link to="/app/cases/new" className="btn-primary">
                  Report UFM Incident
                </Link>
              </>
            ) : null}
          </>
        }
      />

      {error ? (
        <ErrorBanner
          title="Unable to load detections."
          message={error}
          onRetry={() => load()}
        />
      ) : null}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <LoadingState
            compact
            title="Loading detections…"
            detail="Retrieving confirmed detection alerts."
          />
        ) : visible.length === 0 ? (
          <EmptyState
            title={
              filter === "new"
                ? "No unseen detections."
                : "No confirmed detections."
            }
            detail={
              <>
                Start a session on{" "}
                <Link
                  to="/app/monitoring"
                  className="font-semibold text-au-blue"
                >
                  Live Monitoring
                </Link>{" "}
                to capture incidents.
              </>
            }
          />
        ) : (
          <>
            <div className="portal-data-cards">
              {visible.map((d) => {
                const isNew = !d.is_seen;
                return (
                  <div
                    key={d.id}
                    className={[
                      "portal-case-card",
                      isNew ? "ring-1 ring-rose-200 bg-rose-50/40" : "",
                    ].join(" ")}
                    data-affordance="static"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="portal-case-card-title">
                        {formatViolationLabel(d.detection_type)}
                      </p>
                      {isNew ? (
                        <span className="rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                          New
                        </span>
                      ) : (
                        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                          Seen
                        </span>
                      )}
                    </div>
                    <p className="portal-case-card-meta">
                      #{d.id} · {(Number(d.confidence || 0) * 100).toFixed(1)}%
                      {d.camera_id != null ? ` · Camera ${d.camera_id}` : ""}
                    </p>
                    <p className="portal-case-card-meta">
                      {d.timestamp
                        ? formatDateTime(d.timestamp)
                        : "—"}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-3">
                      {isNew ? (
                        <button
                          type="button"
                          onClick={() => onMarkSeen(d.id)}
                          className="text-xs font-semibold text-slate-600 hover:underline"
                        >
                          Mark seen
                        </button>
                      ) : null}
                      {canCreateCase ? (
                        <>
                          <button
                            type="button"
                            onClick={() => openDraft(d)}
                            className="text-xs font-semibold text-au-navy hover:underline"
                          >
                            Create draft case
                          </button>
                          <Link
                            to={`/app/cases/new?detection_id=${d.id}`}
                            onClick={() => {
                              if (isNew) onMarkSeen(d.id);
                            }}
                            className="text-xs font-semibold text-au-blue hover:underline"
                          >
                            File case
                          </Link>
                        </>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="portal-table-wrap portal-table-desktop">
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>ID</th>
                    <th>Type</th>
                    <th className="col-hide-md">Confidence</th>
                    <th className="col-hide-lg">Camera</th>
                    <th className="col-hide-sm">Time</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((d) => {
                    const isNew = !d.is_seen;
                    return (
                      <tr
                        key={d.id}
                        className={isNew ? "bg-rose-50/50" : undefined}
                      >
                        <td>
                          {isNew ? (
                            <span className="rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                              New
                            </span>
                          ) : (
                            <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                              Seen
                            </span>
                          )}
                        </td>
                        <td>{d.id}</td>
                        <td className="font-medium text-au-navy">
                          {formatViolationLabel(d.detection_type)}
                          {!d.is_confirmed ? (
                            <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800">
                              review
                            </span>
                          ) : null}
                        </td>
                        <td className="col-hide-md">
                          {(Number(d.confidence || 0) * 100).toFixed(1)}%
                        </td>
                        <td className="col-hide-lg text-slate-600">
                          {d.camera_id ?? "—"}
                        </td>
                        <td className="col-hide-sm text-xs text-slate-500">
                          {d.timestamp
                            ? formatDateTime(d.timestamp)
                            : "—"}
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-x-2 gap-y-1">
                            {isNew ? (
                              <button
                                type="button"
                                onClick={() => onMarkSeen(d.id)}
                                className="text-xs font-semibold text-slate-600 hover:underline"
                              >
                                Mark seen
                              </button>
                            ) : null}
                            {canCreateCase ? (
                              <>
                                <button
                                  type="button"
                                  onClick={() => openDraft(d)}
                                  className="text-xs font-semibold text-au-navy hover:underline"
                                >
                                  Create draft case
                                </button>
                                <Link
                                  to={`/app/cases/new?detection_id=${d.id}`}
                                  onClick={() => {
                                    if (isNew) onMarkSeen(d.id);
                                  }}
                                  className="text-xs font-semibold text-au-blue hover:underline"
                                >
                                  File case
                                </Link>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {draftFor ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="draft-detection-title"
            className="w-full max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
          >
            <h2
              id="draft-detection-title"
              className="text-lg font-semibold text-au-navy"
            >
              Draft case from detection #{draftFor.id}
            </h2>
            <p className="text-sm text-slate-600">
              {formatViolationLabel(draftFor.detection_type)} ·{" "}
              {(Number(draftFor.confidence || 0) * 100).toFixed(1)}% — attaches
              any auto SNAPSHOT/CLIP evidence.
            </p>
            <label className="block text-sm">
              <span className="portal-label">Student</span>
              <select
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                className="portal-select"
              >
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.student_id} — {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="portal-label">Exam</span>
              <select
                value={examId}
                onChange={(e) => setExamId(e.target.value)}
                className="portal-select"
              >
                {exams.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.course_code} — {e.course_name}
                  </option>
                ))}
              </select>
            </label>
            {draftError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {draftError}
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDraftFor(null)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy || !studentId || !examId}
                onClick={submitDraft}
                className="btn-primary"
              >
                {busy ? "Creating…" : "Create draft"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
