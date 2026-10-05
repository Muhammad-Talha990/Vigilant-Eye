import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import EvidenceFileActions from "../components/EvidenceFileActions";
import ErrorBanner from "../components/ErrorBanner";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import {
  buildCaseTimeline,
  evidenceHasAiSignal,
  evidenceSourceLabel,
  fileNameFromPath,
  formatEvidenceTypeLabel,
  formatReviewActionLabel,
  formatRoleLabel,
  formatResultStatusLabel,
  formatCaseCreatedAt,
  formatStatusLabel,
  formatViolationLabel,
  responsibleLabelForStatus,
  reviewActorLabel,
} from "../config/casePresentation";
import { formatDateTime } from "../config/dateTime";
import { availableReviewActions } from "../config/reviewActions";
import { homePathForRole } from "../config/roleHome";
import {
  EVIDENCE_UPLOAD_ROLES,
  RESULT_CONTROL_ROLES,
  roleIn,
} from "../config/roleAccess";
import {
  actionButtonHint,
  actionMeaning,
  currentStageSummary,
  resolveReviewOutcome,
  resultImpactForCase,
} from "../config/workflowPresentation";
import { useAuth } from "../context/AuthContext";
import {
  createCaseReview,
  fetchCase,
  fetchCaseReviews,
  fetchClarifications,
  fetchEvidence,
  releaseResultControl,
} from "../services/api";

function Field({ label, children }) {
  if (children == null || children === "" || children === "—") return null;
  return (
    <div>
      <dt className="portal-meta-label">{label}</dt>
      <dd className="portal-meta-value">{children}</dd>
    </div>
  );
}

function Section({ title, children, actions, className = "" }) {
  return (
    <section className={`portal-card overflow-hidden ${className}`.trim()}>
      <div className="portal-panel-header">
        <h2 className="portal-section-title">{title}</h2>
        {actions || null}
      </div>
      <div className="portal-panel-body">{children}</div>
    </section>
  );
}

export default function CaseDetailPage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const isStudent = user?.role === "STUDENT";
  const canManageResultHold = roleIn(user?.role, RESULT_CONTROL_ROLES);
  const canUploadEvidence = roleIn(user?.role, EVIDENCE_UPLOAD_ROLES);
  const [caseData, setCaseData] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [clarifications, setClarifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [remarks, setRemarks] = useState("");
  const [signerName, setSignerName] = useState(user?.name || "");
  const [signatureAck, setSignatureAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [releaseBusy, setReleaseBusy] = useState(false);
  const [confirmReleaseHold, setConfirmReleaseHold] = useState(false);
  const [resultMessage, setResultMessage] = useState("");
  const reviewDialogRef = useRef(null);
  const reviewCancelRef = useRef(null);
  const releaseDialogRef = useRef(null);
  const releaseCancelRef = useRef(null);
  const previouslyFocused = useRef(null);

  function leaveAfterReviewAction() {
    const from = location.state?.from;
    if (typeof from === "string" && from.startsWith("/app")) {
      navigate(from, { replace: true });
      return;
    }
    if (typeof window !== "undefined" && window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate(homePathForRole(user?.role), { replace: true });
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const casePromise = fetchCase(caseId);
      const evidencePromise = fetchEvidence(caseId);
      const clarPromise = fetchClarifications(caseId).catch(() => []);
      const reviewsPromise = isStudent
        ? Promise.resolve([])
        : fetchCaseReviews(caseId);

      const [c, r, e, clar] = await Promise.all([
        casePromise,
        reviewsPromise,
        evidencePromise,
        clarPromise,
      ]);
      setCaseData(c);
      setReviews(Array.isArray(r) ? r : []);
      setEvidence(Array.isArray(e) ? e : []);
      setClarifications(Array.isArray(clar) ? clar : []);
    } catch {
      setError("Unable to load this UFM case. Please try again.");
      setCaseData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, isStudent]);

  useEffect(() => {
    if (user?.name) setSignerName((prev) => prev || user.name);
  }, [user?.name]);

  useEffect(() => {
    const open = Boolean(confirmAction) || confirmReleaseHold;
    if (!open) return undefined;
    previouslyFocused.current = document.activeElement;
    const panel = confirmAction ? reviewDialogRef.current : releaseDialogRef.current;
    const cancelBtn = confirmAction ? reviewCancelRef.current : releaseCancelRef.current;
    const focusTimer = window.setTimeout(() => cancelBtn?.focus(), 0);

    function onKey(e) {
      if (e.key === "Escape" && !busy && !releaseBusy) {
        e.preventDefault();
        if (confirmAction) setConfirmAction(null);
        if (confirmReleaseHold) setConfirmReleaseHold(false);
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const focusable = panel.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      const list = Array.from(focusable).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", onKey);
      const prev = previouslyFocused.current;
      if (prev && typeof prev.focus === "function") prev.focus();
    };
  }, [confirmAction, confirmReleaseHold, busy, releaseBusy]);

  const actions = caseData
    ? availableReviewActions(user?.role, caseData.status)
    : [];

  const hasSubmittedClarification = clarifications.length > 0;

  const timeline = useMemo(
    () =>
      buildCaseTimeline({
        caseData,
        reviews,
        evidence,
        clarifications,
        includeReviews: !isStudent,
        includeEvidence: true,
        includeClarifications: true,
        includeCreateSignOff: !isStudent,
        includeReporterDetail: !isStudent,
        includeResponsibleDetail: !isStudent,
      }),
    [caseData, reviews, evidence, clarifications, isStudent]
  );

  async function runAction(action) {
    setActionError("");
    if (!signatureAck || !signerName.trim()) {
      setActionError("Digital sign-off (name + acknowledgment) is required.");
      setConfirmAction(null);
      return;
    }
    setBusy(true);
    try {
      await createCaseReview(caseId, {
        action,
        remarks: remarks.trim() || `${action} from portal`,
        signer_name: signerName.trim(),
        signature_ack: true,
      });
      setRemarks("");
      setSignatureAck(false);
      setConfirmAction(null);
      if (action === "FORWARD" || action === "RETURN") {
        leaveAfterReviewAction();
        return;
      }
      await load();
    } catch (err) {
      setActionError(err.message || "Review action failed. Please try again.");
      setConfirmAction(null);
    } finally {
      setBusy(false);
    }
  }

  function requestAction(action) {
    setActionError("");
    if (!signerName.trim() || !signatureAck) {
      setActionError(
        "Complete digital sign-off (typed name and acknowledgment) before continuing."
      );
      requestAnimationFrame(() => {
        document
          .getElementById("case-review-action-error")
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      return;
    }
    setConfirmAction(action);
  }

  async function runReleaseHold() {
    const rc = caseData?.result_control;
    if (!rc?.id || !canManageResultHold) return;
    setReleaseBusy(true);
    setActionError("");
    setResultMessage("");
    try {
      await releaseResultControl(rc.id);
      setConfirmReleaseHold(false);
      setResultMessage("RESULT HOLD RELEASED — result status is now Released.");
      await load();
    } catch (err) {
      setActionError(err.message || "Unable to release result hold.");
      setConfirmReleaseHold(false);
    } finally {
      setReleaseBusy(false);
    }
  }

  const latestDecision = useMemo(() => {
    if (!reviews.length) return null;
    const decisive = [...reviews]
      .reverse()
      .find((r) => r.action === "APPROVE" || r.action === "REJECT");
    return decisive || null;
  }, [reviews]);

  if (loading) {
    return <LoadingState label="Loading UFM case…" />;
  }

  if (error) {
    return (
      <div className="space-y-3">
        <ErrorBanner title="Unable to load UFM case." message={error} onRetry={load} />
        <Link to="/app/cases" className="btn-ghost">
          ← Back to cases
        </Link>
      </div>
    );
  }

  if (!caseData) return null;

  const responsible = responsibleLabelForStatus(caseData.status);
  const stage = currentStageSummary(caseData.status);
  const confirmLabel = confirmAction
    ? formatReviewActionLabel(confirmAction)
    : "";
  const confirmOutcome =
    confirmAction && user?.role
      ? resolveReviewOutcome(user.role, caseData.status, confirmAction)
      : null;
  const actionOutcomes = actions.map((action) => ({
    action,
    outcome: resolveReviewOutcome(user?.role, caseData.status, action),
  }));

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5">
      <PageHeader
        breadcrumb={`Home / ${isStudent ? "My Cases" : "Cases"} / ${caseData.case_number}`}
        title={caseData.case_number}
        description={
          !isStudent && responsible
            ? `Current review responsibility: ${responsible}`
            : "Review case details, supporting evidence, remarks, and workflow status."
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={caseData.status} />
            <Link to="/app/cases" className="btn-secondary btn-sm">
              Back to list
            </Link>
          </div>
        }
      />

      {/* CASE IDENTITY */}
      <div className="portal-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Case identity
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={caseData.status} />
              {!isStudent && responsible ? (
                <span className="text-xs text-slate-600">
                  Current review:{" "}
                  <span className="font-semibold text-slate-800">
                    {responsible}
                  </span>
                </span>
              ) : null}
            </div>
            <dl className="portal-meta-grid mt-4">
              <Field label="Created">
                {caseData.created_at
                  ? formatCaseCreatedAt(caseData.created_at)
                  : null}
              </Field>
              <Field label="Last updated">
                {caseData.updated_at
                  ? formatDateTime(caseData.updated_at)
                  : null}
              </Field>
              {!isStudent ? (
                <Field label="Reported by">
                  {[
                    caseData.reporter_name || null,
                    caseData.reporter_role
                      ? formatRoleLabel(caseData.reporter_role)
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || null}
                </Field>
              ) : null}
            </dl>
          </div>
          <div className="flex flex-wrap gap-2">
            {isStudent ? (
              hasSubmittedClarification ? (
                <span className="rounded-md border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-600">
                  Clarification already submitted
                </span>
              ) : (
                <Link
                  to={`/app/clarification?case_id=${caseData.id}`}
                  className="btn-primary"
                >
                  Submit Clarification
                </Link>
              )
            ) : (
              <Link
                to={`/app/evidence?case_id=${caseData.id}`}
                className="btn-secondary"
              >
                {canUploadEvidence ? "Manage evidence" : "View evidence"}
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* WORKFLOW STAGE — derived from real backend workflow tables */}
      <section className="portal-card overflow-hidden" data-affordance="static">
        <div className="portal-panel-header">
          <h2 className="portal-section-title">What happens next?</h2>
          <StatusBadge status={caseData.status} />
        </div>
        <div className="portal-panel-body space-y-4">
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Current stage
              </dt>
              <dd className="mt-0.5 text-sm font-semibold text-au-navy">
                {stage.statusLabel}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Current responsibility
              </dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                {stage.responsibility}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Result impact (current)
              </dt>
              <dd className="mt-0.5 text-sm font-medium text-slate-800">
                {resultImpactForCase(caseData)}
              </dd>
            </div>
          </dl>
          {stage.note ? (
            <p className="text-sm text-slate-600">{stage.note}</p>
          ) : null}

          {!isStudent && actionOutcomes.length > 0 ? (
            <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Available actions
              </p>
              <ul className="mt-2 space-y-2">
                {actionOutcomes.map(({ action, outcome }) => (
                  <li key={action} className="text-sm text-slate-700">
                    <span className="font-semibold text-au-navy">
                      {formatReviewActionLabel(action)}
                    </span>
                    {outcome ? (
                      <span className="text-slate-600">
                        {" "}
                        → {formatStatusLabel(outcome.nextStatus)}
                        {outcome.nextRole
                          ? ` · next: ${formatRoleLabel(outcome.nextRole)}`
                          : outcome.isFinal
                            ? " · final decision"
                            : ""}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                Return always sets status to Pending (HOD restarts the chain). It
                does not mean “return only to the previous reviewer.”
              </p>
            </div>
          ) : null}

          {isStudent ? (
            <div className="rounded-lg border border-sky-100 bg-sky-50 px-3 py-3 text-sm text-sky-950">
              {stage.isFinal ? (
                <p>
                  A final committee decision is on record (
                  {formatStatusLabel(caseData.status)}). Refer to Result Control
                  below for examination result hold status.
                </p>
              ) : (
                <p>
                  Staff are reviewing this case
                  {responsible ? ` (${responsible})` : ""}. Clarification may be
                  submitted if not already on record. Forward, Return, Approve,
                  and Reject are staff actions only.
                </p>
              )}
            </div>
          ) : null}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* STUDENT */}
        <Section title="Student">
          <dl className="portal-meta-grid">
            <Field label="Name">{caseData.student_name || "—"}</Field>
            <Field label="Student ID">
              {caseData.student_roll || "—"}
            </Field>
            <Field label="Department">
              {caseData.student_department || null}
            </Field>
            <Field label="Program">{caseData.student_program || null}</Field>
          </dl>
        </Section>

        {/* EXAMINATION */}
        <Section title="Examination">
          <dl className="portal-meta-grid">
            <Field label="Course code">
              {caseData.exam_course_code || null}
            </Field>
            <Field label="Course">{caseData.exam_course_name || null}</Field>
            <Field label="Semester">{caseData.exam_semester || null}</Field>
            <Field label="Exam date">{caseData.exam_date || null}</Field>
            <Field label="Exam room">
              {[
                caseData.room_number ? `Room ${caseData.room_number}` : null,
                caseData.room_building || null,
              ]
                .filter(Boolean)
                .join(" · ") || null}
            </Field>
            <Field label="Camera">
              {caseData.camera_code || caseData.camera_name
                ? [
                    caseData.camera_code || null,
                    caseData.camera_name || null,
                  ]
                    .filter(Boolean)
                    .join(" — ")
                : caseData.camera_id != null
                  ? `Camera #${caseData.camera_id}`
                  : "Not recorded"}
            </Field>
            {!isStudent ? (
              <Field label="Reported by">
                {caseData.reporter_name
                  ? `${caseData.reporter_name}${
                      caseData.reporter_role
                        ? ` (${formatRoleLabel(caseData.reporter_role)})`
                        : ""
                    }`
                  : null}
              </Field>
            ) : null}
          </dl>
        </Section>
      </div>

      {/* RESULT CONTROL — separate from UFM case status */}
      {caseData.result_control ? (
        <Section
          title="Result control"
          actions={
            <span
              className={[
                "inline-flex items-center rounded-md px-2.5 py-1 text-xs font-bold uppercase tracking-wide ring-1 ring-inset",
                caseData.result_control.result_status === "HELD"
                  ? "bg-amber-100 text-amber-950 ring-amber-300"
                  : "bg-emerald-100 text-emerald-950 ring-emerald-300",
              ].join(" ")}
            >
              {formatResultStatusLabel(caseData.result_control.result_status)}
            </span>
          }
        >
          <p className="mb-3 text-sm text-slate-600">
            Result status is separate from this case&apos;s workflow status (
            {formatStatusLabel(caseData.status)}). A hold is created when the
            committee Approves a case; Return / Reject do not clear an existing
            hold by themselves.
          </p>
          {resultMessage ? (
            <div
              role="status"
              className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900"
            >
              {resultMessage}
            </div>
          ) : null}
          <dl className="portal-meta-grid">
            <Field label="Result status">
              {formatResultStatusLabel(caseData.result_control.result_status)}
            </Field>
            <Field label="Transcript">
              {formatStatusLabel(caseData.result_control.transcript_status)}
            </Field>
            <Field label="Student">
              {caseData.result_control.student_name ||
                caseData.student_name ||
                null}
            </Field>
            <Field label="Roll number">
              {caseData.result_control.student_roll ||
                caseData.student_roll ||
                null}
            </Field>
            <Field label="Source case">
              {caseData.result_control.case_number || caseData.case_number}
            </Field>
            <Field label="Reason">
              {caseData.result_control.reason || null}
            </Field>
            <Field label="Placed by">
              {caseData.result_control.held_by_name ||
                (caseData.result_control.held_by != null
                  ? `User #${caseData.result_control.held_by}`
                  : null)}
            </Field>
            <Field label="Placed at">
              {caseData.result_control.held_at
                ? formatDateTime(caseData.result_control.held_at)
                : null}
            </Field>
            {caseData.result_control.result_status === "RELEASED" ? (
              <>
                <Field label="Released by">
                  {caseData.result_control.released_by_name ||
                    (caseData.result_control.released_by != null
                      ? `User #${caseData.result_control.released_by}`
                      : null)}
                </Field>
                <Field label="Released at">
                  {caseData.result_control.released_at
                    ? formatDateTime(caseData.result_control.released_at)
                    : null}
                </Field>
              </>
            ) : null}
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            {canManageResultHold ? (
              <Link to="/app/result-controls" className="btn-secondary btn-sm">
                View Result Controls
              </Link>
            ) : null}
            {canManageResultHold &&
            caseData.result_control.result_status === "HELD" ? (
              <button
                type="button"
                disabled={releaseBusy}
                onClick={() => setConfirmReleaseHold(true)}
                className="btn-danger btn-sm"
              >
                Release Result Hold
              </button>
            ) : null}
            {isStudent && caseData.result_control.result_status === "HELD" ? (
              <p className="self-center text-xs text-slate-500">
                The examination result is on hold because of this UFM case.
                Contact the Exam Department regarding release.
              </p>
            ) : null}
          </div>
        </Section>
      ) : caseData.status === "APPROVED" ? (
        <Section title="Result control">
          <p className="text-sm text-slate-600">
            This case is Approved. If a result hold was recorded, it will appear
            here. No hold record is currently linked to this case.
          </p>
        </Section>
      ) : caseData.status === "REJECTED" ? (
        <Section title="Result control">
          <p className="text-sm text-slate-600">
            This case was Rejected. Rejecting a case does not create a result
            hold. No result-control record is linked to this case.
          </p>
        </Section>
      ) : (
        <Section title="Result control">
          <p className="text-sm text-slate-600">
            No result hold is linked to this case yet. A hold is applied
            automatically only when the UFM Committee Approves the case.
          </p>
        </Section>
      )}

      {/* UFM INCIDENT */}
      <Section title="UFM Incident">
        <dl className="grid gap-3 sm:grid-cols-2">
          <Field label="Violation type">
            {formatViolationLabel(caseData.violation_type)}
          </Field>
          <Field label="Incident recorded">
            {caseData.created_at
              ? formatCaseCreatedAt(caseData.created_at)
              : null}
          </Field>
          {Array.isArray(caseData.recovered_materials) &&
          caseData.recovered_materials.length > 0 ? (
            <div className="sm:col-span-2">
              <Field label="Recovered / confiscated material">
                <span className="font-normal text-slate-800">
                  {caseData.recovered_materials
                    .map((code) => {
                      const labels = {
                        ANSWER_EXTRA_SHEET: "Answer / extra sheet",
                        MOBILE_PHONE: "Mobile phone",
                        CALCULATOR: "Calculator",
                        MATERIAL_ON_BODY:
                          "Material written on body/body part",
                        SMART_DEVICES: "Smart devices",
                        OTHER: "Other cheating material",
                      };
                      return labels[code] || String(code).replaceAll("_", " ");
                    })
                    .join("; ")}
                  {caseData.recovered_other_detail
                    ? ` — ${caseData.recovered_other_detail}`
                    : ""}
                </span>
              </Field>
            </div>
          ) : null}
          <div className="sm:col-span-2">
            <Field label="Description">
              <span className="whitespace-pre-wrap font-normal text-slate-800">
                {caseData.description}
              </span>
            </Field>
          </div>
          {!isStudent && caseData.remarks ? (
            <div className="sm:col-span-2">
              <Field label="Remarks">
                <span className="whitespace-pre-wrap font-normal text-slate-800">
                  {caseData.remarks}
                </span>
              </Field>
            </div>
          ) : null}
          {!isStudent && caseData.signer_name ? (
            <Field label="Create sign-off">
              {[
                caseData.signer_name,
                caseData.signed_at
                  ? formatDateTime(caseData.signed_at)
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </Field>
          ) : null}
        </dl>
        {!isStudent && evidence.some((e) => evidenceHasAiSignal(e)) ? (
          <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-900">
            <p className="font-semibold">
              System-assisted / AI-generated information
            </p>
            <p className="mt-1">
              Confidence scores and detection links below are system-assisted
              signals for reviewers. They are not a final disciplinary judgment.
            </p>
          </div>
        ) : null}
      </Section>

      {/* EVIDENCE */}
      <Section
        title="Evidence for this case"
        actions={
          !isStudent ? (
            <Link
              to={`/app/evidence?case_id=${caseData.id}`}
              className="text-xs font-semibold text-au-blue hover:underline"
            >
              {canUploadEvidence ? "Manage evidence" : "View evidence"}
            </Link>
          ) : null
        }
      >
        {evidence.length === 0 ? (
          <p className="text-sm text-slate-500">
            No evidence is attached to {caseData.case_number} yet.
          </p>
        ) : (
          <div className="portal-table-wrap">
            <table className="portal-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th className="col-hide-md">Source</th>
                  <th className="col-hide-lg">File</th>
                  <th className="col-hide-sm">Captured</th>
                  {!isStudent ? (
                    <th className="col-hide-lg">Uploaded by</th>
                  ) : null}
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium text-au-navy">#{e.id}</td>
                    <td>{formatEvidenceTypeLabel(e.evidence_type)}</td>
                    <td className="col-hide-md cell-wrap text-xs text-slate-600">
                      {evidenceSourceLabel(e)}
                    </td>
                    <td className="col-hide-lg cell-clip text-xs text-slate-600" title={fileNameFromPath(e.file_path) || ""}>
                      {fileNameFromPath(e.file_path) || "—"}
                    </td>
                    <td className="col-hide-sm text-xs text-slate-500">
                      {e.timestamp
                        ? formatDateTime(e.timestamp)
                        : "—"}
                    </td>
                    {!isStudent ? (
                      <td className="col-hide-lg text-xs text-slate-500">
                        {e.uploaded_by != null ? `User #${e.uploaded_by}` : "—"}
                      </td>
                    ) : null}
                    <td>
                      <EvidenceFileActions
                        evidenceId={e.id}
                        onError={(msg) => setActionError(msg)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* TIMELINE */}
      <Section title="Case timeline">
        {timeline.length === 0 ? (
          <p className="text-sm text-slate-500">No timeline events available.</p>
        ) : (
          <ol className="relative space-y-0 border-l border-slate-200 ml-2">
            {timeline.map((ev) => (
              <li key={ev.id} className="relative pb-5 pl-5 last:pb-0">
                <span
                  className={[
                    "absolute -left-1.5 top-1.5 h-3 w-3 rounded-full border-2 border-white",
                    ev.current ? "bg-au-navy" : "bg-slate-300",
                  ].join(" ")}
                />
                <p className="text-sm font-semibold text-au-navy">{ev.title}</p>
                {ev.detail ? (
                  <p className="mt-0.5 text-sm text-slate-600">{ev.detail}</p>
                ) : null}
                <p className="mt-0.5 text-xs text-slate-400">
                  {ev.at ? formatDateTime(ev.at) : ""}
                </p>
              </li>
            ))}
          </ol>
        )}
      </Section>

      {/* CLARIFICATIONS */}
      <Section title="Student clarifications">
        {clarifications.length === 0 ? (
          <p className="text-sm text-slate-500">
            {isStudent
              ? "No clarification has been submitted for this case yet."
              : "No clarifications submitted for this case yet."}
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 -mx-5">
            {clarifications.map((c) => (
              <li key={c.id} className="px-5 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={c.status} />
                  <span className="text-xs text-slate-400">
                    {c.created_at
                      ? formatDateTime(c.created_at)
                      : ""}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-slate-700">
                  {c.statement}
                </p>
              </li>
            ))}
          </ul>
        )}
        {isStudent ? (
          hasSubmittedClarification ? (
            <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-sm font-semibold text-au-navy">
                Clarification already submitted.
              </p>
              <p className="mt-1 text-sm text-slate-600">
                The clarification is on the case record. An additional
                clarification cannot be submitted for this case.
              </p>
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3">
              <p className="text-sm font-semibold text-sky-900">
                Clarification / Required Actions
              </p>
              <p className="mt-1 text-sm text-sky-800">
                A written clarification may be submitted for this UFM case.
                Staff are notified when it is recorded.
              </p>
              <Link
                to={`/app/clarification?case_id=${caseData.id}`}
                className="mt-2 inline-block text-sm font-semibold text-au-blue hover:underline"
              >
                Submit clarification →
              </Link>
            </div>
          )
        ) : null}
      </Section>

      {/* REVIEW / DECISION — DEC stacks with actions on top */}
      {!isStudent ? (
        <div
          className={
            user?.role === "DEC"
              ? "grid gap-5"
              : "grid gap-5 lg:grid-cols-2"
          }
        >
          <Section
            title="Review history & decisions"
            className={user?.role === "DEC" ? "order-2" : ""}
          >
            {caseData.status === "APPROVED" ||
            caseData.status === "REJECTED" ||
            latestDecision ? (
              <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Current decision status
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StatusBadge status={caseData.status} />
                  {latestDecision ? (
                    <span className="font-semibold text-au-navy">
                      {formatReviewActionLabel(latestDecision.action)}
                    </span>
                  ) : null}
                </div>
                {latestDecision ? (
                  <dl className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                    <div>
                      <dt className="uppercase tracking-wide text-slate-400">
                        Reviewer
                      </dt>
                      <dd className="font-medium text-slate-800">
                        {reviewActorLabel(latestDecision)}
                      </dd>
                    </div>
                    <div>
                      <dt className="uppercase tracking-wide text-slate-400">
                        Role
                      </dt>
                      <dd className="font-medium text-slate-800">
                        {formatRoleLabel(latestDecision.reviewer_role)}
                      </dd>
                    </div>
                    {latestDecision.remarks ? (
                      <div className="sm:col-span-2">
                        <dt className="uppercase tracking-wide text-slate-400">
                          Reason / comment
                        </dt>
                        <dd className="mt-0.5 text-slate-800">
                          {latestDecision.remarks}
                        </dd>
                      </div>
                    ) : null}
                    <div className="sm:col-span-2">
                      <dt className="uppercase tracking-wide text-slate-400">
                        Date / time
                      </dt>
                      <dd>
                        {latestDecision.created_at
                          ? formatDateTime(latestDecision.created_at)
                          : "—"}
                      </dd>
                    </div>
                  </dl>
                ) : null}
              </div>
            ) : null}

            {reviews.length === 0 ? (
              <p className="text-sm text-slate-500">
                No review decisions recorded yet.
              </p>
            ) : (
              <ul className="space-y-3">
                {reviews.map((r) => (
                  <li
                    key={r.id}
                    className="rounded-lg border border-slate-100 bg-white px-3 py-3 text-sm shadow-sm"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-au-navy">
                        {formatReviewActionLabel(r.action)}
                      </span>
                      <span className="text-xs text-slate-500">
                        {formatRoleLabel(r.reviewer_role)}
                      </span>
                    </div>
                    <dl className="mt-2 grid gap-1 text-xs text-slate-600">
                      <div>
                        <span className="text-slate-400">Reviewer: </span>
                        {reviewActorLabel(r)}
                      </div>
                      {r.remarks ? (
                        <div>
                          <span className="text-slate-400">
                            Reason / comment:{" "}
                          </span>
                          <span className="text-slate-800">{r.remarks}</span>
                        </div>
                      ) : null}
                      <div>
                        <span className="text-slate-400">Date: </span>
                        {r.created_at
                          ? formatDateTime(r.created_at)
                          : "—"}
                      </div>
                      {r.signer_name ? (
                        <div>
                          <span className="text-slate-400">Sign-off: </span>
                          {r.signer_name}
                          {r.signed_at
                            ? ` · ${formatDateTime(r.signed_at)}`
                            : ""}
                        </div>
                      ) : null}
                    </dl>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section
            title="Review actions"
            className={user?.role === "DEC" ? "order-1" : ""}
          >
            <p className="mb-3 text-sm text-slate-600">
              Acting as{" "}
              <span className="font-semibold text-slate-800">
                {user?.name || "Current user"}
              </span>{" "}
              ({formatRoleLabel(user?.role)}) on case{" "}
              <span className="font-semibold text-au-navy">
                {caseData.case_number}
              </span>{" "}
              · status{" "}
              <span className="font-semibold">
                {formatStatusLabel(caseData.status)}
              </span>
              .
            </p>
            {actions.length === 0 ? (
              <p className="text-sm text-slate-500">
                No workflow actions are available for this role on this status.
                {stage.isFinal
                  ? " A final decision is already recorded."
                  : responsible
                    ? ` Current responsibility: ${responsible}.`
                    : ""}
              </p>
            ) : (
              <div className="space-y-3">
                <label className="block">
                  <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                    Remarks / reason
                  </span>
                  <textarea
                    rows={3}
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    placeholder="Optional remarks recorded with this action (API allows empty; recommended for Return)"
                    className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm"
                  />
                </label>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Digital sign-off
                  </p>
                  <p className="text-xs text-slate-500">
                    Required before Forward, Return, Approve, or Reject.
                  </p>
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-slate-600">
                      Full name for digital sign-off
                    </span>
                    <input
                      value={signerName}
                      onChange={(e) => setSignerName(e.target.value)}
                      placeholder="Type your full name"
                      autoComplete="name"
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </label>
                  <label className="flex items-start gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={signatureAck}
                      onChange={(e) => setSignatureAck(e.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      I certify this review action and accept audit recording of
                      my name and timestamp.
                    </span>
                  </label>
                </div>

                {actionError ? (
                  <div
                    id="case-review-action-error"
                    className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                    role="alert"
                  >
                    {actionError}
                  </div>
                ) : null}

                <div className="grid gap-2 sm:grid-cols-2">
                  {actionOutcomes.map(({ action, outcome }) => (
                    <button
                      key={action}
                      type="button"
                      disabled={busy}
                      onClick={() => requestAction(action)}
                      className={[
                        "portal-review-action rounded-lg px-4 py-3 text-left text-sm font-semibold text-white disabled:opacity-60",
                        action === "REJECT" || action === "RETURN"
                          ? "bg-rose-600 hover:bg-rose-500"
                          : action === "APPROVE"
                            ? "bg-emerald-600 hover:bg-emerald-500"
                            : "bg-au-navy hover:bg-sky-800",
                      ].join(" ")}
                    >
                      <span className="block">
                        {formatReviewActionLabel(action)}
                      </span>
                      <span className="mt-0.5 block text-xs font-normal text-white/90">
                        {actionButtonHint(action) ||
                          actionMeaning(action).slice(0, 72)}
                      </span>
                      {outcome ? (
                        <span className="mt-1 block text-[11px] font-normal text-white/80">
                          → {formatStatusLabel(outcome.nextStatus)}
                          {outcome.nextRole
                            ? ` · ${formatRoleLabel(outcome.nextRole)}`
                            : ""}
                        </span>
                      ) : null}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Section>
        </div>
      ) : (
        <Section title="Available actions">
          <p className="text-sm text-slate-600">
            {hasSubmittedClarification
              ? "Clarification is already on record. Refer to Help and Guidance or Notifications for updates."
              : "Submit clarification for this case, or open Help and Guidance for portal reference."}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {hasSubmittedClarification ? (
              <span className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-600">
                Clarification already submitted.
              </span>
            ) : (
              <Link
                to={`/app/clarification?case_id=${caseData.id}`}
                className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
              >
                Clarification / Required Actions
              </Link>
            )}
            <Link
              to="/app/notifications"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Notifications
            </Link>
            <Link
              to="/app/help"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Help and Guidance
            </Link>
          </div>
        </Section>
      )}

      {/* Confirmation dialog */}
      {confirmReleaseHold && caseData?.result_control ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div
            ref={releaseDialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="release-case-hold-title"
            className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
          >
            <h3
              id="release-case-hold-title"
              className="text-lg font-semibold text-au-navy"
            >
              Release result hold for this student?
            </h3>
            <dl className="mt-3 space-y-1 text-sm text-slate-700">
              <div>
                <span className="text-slate-400">Student: </span>
                {caseData.result_control.student_name ||
                  caseData.student_name ||
                  "—"}
              </div>
              <div>
                <span className="text-slate-400">Roll number: </span>
                {caseData.result_control.student_roll ||
                  caseData.student_roll ||
                  "—"}
              </div>
              <div>
                <span className="text-slate-400">UFM case: </span>
                {caseData.case_number}
              </div>
              <div>
                <span className="text-slate-400">Current status: </span>
                {formatResultStatusLabel(caseData.result_control.result_status)}
              </div>
            </dl>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                ref={releaseCancelRef}
                type="button"
                disabled={releaseBusy}
                onClick={() => setConfirmReleaseHold(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={releaseBusy}
                onClick={runReleaseHold}
                className="btn-danger"
              >
                {releaseBusy ? "Releasing…" : "Release Hold"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {confirmAction ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div
            ref={reviewDialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-review-title"
            className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
          >
            <h3
              id="confirm-review-title"
              className="text-lg font-semibold text-au-navy"
            >
              {confirmLabel} UFM Case {caseData.case_number}?
            </h3>
            {confirmOutcome ? (
              <p className="mt-2 text-sm text-slate-600">
                {confirmOutcome.meaning}
              </p>
            ) : null}
            <dl className="mt-3 space-y-1 text-sm text-slate-600">
              <div>
                <span className="text-slate-400">Action: </span>
                <span className="font-semibold text-slate-800">
                  {confirmLabel}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Case: </span>
                <span className="font-semibold text-slate-800">
                  {caseData.case_number}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Current status: </span>
                {formatStatusLabel(caseData.status)}
              </div>
              {confirmOutcome ? (
                <>
                  <div>
                    <span className="text-slate-400">After this action: </span>
                    <span className="font-semibold text-slate-800">
                      {formatStatusLabel(confirmOutcome.nextStatus)}
                      {confirmOutcome.isFinal ? " (final)" : ""}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Next responsible: </span>
                    <span className="font-semibold text-slate-800">
                      {confirmOutcome.nextRole
                        ? formatRoleLabel(confirmOutcome.nextRole)
                        : "None — workflow complete"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Result control: </span>
                    {confirmOutcome.resultImpact}
                  </div>
                </>
              ) : null}
              <div>
                <span className="text-slate-400">Performed by: </span>
                {signerName.trim()} ({formatRoleLabel(user?.role)})
              </div>
            </dl>
            <p className="mt-3 text-sm text-slate-600">
              The reporter and linked student receive a status notification.
              Digital sign-off is stored for audit.
            </p>
            {remarks.trim() ? (
              <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <span className="font-semibold">Remarks: </span>
                {remarks.trim()}
              </p>
            ) : (
              <p className="mt-3 text-xs text-slate-500">
                No remarks entered — a default audit note will be stored.
              </p>
            )}
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                ref={reviewCancelRef}
                type="button"
                disabled={busy}
                onClick={() => setConfirmAction(null)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction(confirmAction)}
                className={[
                  confirmAction === "REJECT" || confirmAction === "RETURN"
                    ? "btn-danger"
                    : confirmAction === "APPROVE"
                      ? "btn-success"
                      : "btn-primary",
                ].join(" ")}
              >
                {busy ? "Submitting…" : `Confirm ${confirmLabel}`}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
