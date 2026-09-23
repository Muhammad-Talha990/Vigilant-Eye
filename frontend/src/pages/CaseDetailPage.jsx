import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import { availableReviewActions } from "../config/reviewActions";
import { useAuth } from "../context/AuthContext";
import {
  createCaseReview,
  fetchCase,
  fetchCaseReviews,
  fetchClarifications,
  fetchEvidence,
  openEvidenceFile,
  downloadEvidenceFile,
} from "../services/api";

export default function CaseDetailPage() {
  const { caseId } = useParams();
  const { user } = useAuth();
  const isStudent = user?.role === "STUDENT";
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

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [c, r, e, clar] = await Promise.all([
        fetchCase(caseId),
        fetchCaseReviews(caseId),
        fetchEvidence(caseId),
        fetchClarifications(caseId).catch(() => []),
      ]);
      setCaseData(c);
      setReviews(Array.isArray(r) ? r : []);
      setEvidence(Array.isArray(e) ? e : []);
      setClarifications(Array.isArray(clar) ? clar : []);
    } catch (err) {
      setError(err.message || "Failed to load case");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [caseId]);

  useEffect(() => {
    if (user?.name) setSignerName((prev) => prev || user.name);
  }, [user?.name]);

  const actions = caseData
    ? availableReviewActions(user?.role, caseData.status)
    : [];

  async function runAction(action) {
    setActionError("");
    if (!signatureAck || !signerName.trim()) {
      setActionError("Digital sign-off (name + acknowledgment) is required.");
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
      await load();
    } catch (err) {
      setActionError(err.message || "Review action failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-slate-500">Loading case...</p>;
  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!caseData) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">
            <Link to="/app/cases" className="text-au-blue">
              Cases
            </Link>{" "}
            / Detail
          </p>
          <h1 className="text-2xl font-semibold text-au-navy">
            {caseData.case_number}
          </h1>
          <div className="mt-2">
            <StatusBadge status={caseData.status} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {isStudent ? (
            <Link
              to={`/app/clarification?case_id=${caseData.id}`}
              className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
            >
              Submit Clarification
            </Link>
          ) : (
            <Link
              to={`/app/evidence?case_id=${caseData.id}`}
              className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800"
            >
              Upload Evidence
            </Link>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-au-navy">Case Information</h2>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">Violation</dt>
              <dd className="font-medium">{caseData.violation_type}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Student</dt>
              <dd className="font-medium">
                {caseData.student_name || "—"}{" "}
                <span className="text-slate-500">
                  ({caseData.student_roll || caseData.student_id})
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Department / Program</dt>
              <dd className="font-medium">
                {caseData.student_department || "—"}
                {caseData.student_program
                  ? ` · ${caseData.student_program}`
                  : ""}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Exam</dt>
              <dd className="font-medium">
                {caseData.exam_course_code || "—"}{" "}
                {caseData.exam_course_name
                  ? `— ${caseData.exam_course_name}`
                  : ""}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Exam date / Room</dt>
              <dd className="font-medium">
                {caseData.exam_date || "—"}
                {caseData.room_number
                  ? ` · Room ${caseData.room_number}`
                  : ""}
                {caseData.room_building ? ` (${caseData.room_building})` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Reported by</dt>
              <dd className="font-medium">
                {caseData.reporter_name || `User #${caseData.reported_by}`}
                {caseData.reporter_role
                  ? ` · ${caseData.reporter_role}`
                  : ""}
              </dd>
            </div>
            {caseData.signer_name ? (
              <div className="sm:col-span-2">
                <dt className="text-slate-500">Create sign-off</dt>
                <dd className="font-medium">
                  {caseData.signer_name}
                  {caseData.signed_at
                    ? ` · ${new Date(caseData.signed_at).toLocaleString()}`
                    : ""}
                </dd>
              </div>
            ) : null}
            <div className="sm:col-span-2">
              <dt className="text-slate-500">Description</dt>
              <dd className="mt-1 whitespace-pre-wrap text-slate-800">
                {caseData.description}
              </dd>
            </div>
            {caseData.remarks ? (
              <div className="sm:col-span-2">
                <dt className="text-slate-500">Remarks</dt>
                <dd className="mt-1 whitespace-pre-wrap text-slate-800">
                  {caseData.remarks}
                </dd>
              </div>
            ) : null}
          </dl>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-au-navy">
            {isStudent ? "Your Options" : "Review Actions"}
          </h2>
          {isStudent ? (
            <div className="mt-3 space-y-3 text-sm text-slate-600">
              <p>
                You can submit a written clarification for this case. Staff will
                be notified automatically.
              </p>
              <Link
                to={`/app/clarification?case_id=${caseData.id}`}
                className="inline-flex rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
              >
                Write Clarification
              </Link>
              <Link
                to="/app/help"
                className="ml-2 inline-flex rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
              >
                Help & Guidelines
              </Link>
            </div>
          ) : actions.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">
              No workflow actions available for your role on this status.
            </p>
          ) : (
            <div className="mt-3 space-y-3">
              <textarea
                rows={3}
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Optional remarks for this action"
                className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-sm"
              />
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Digital sign-off
                </p>
                <input
                  value={signerName}
                  onChange={(e) => setSignerName(e.target.value)}
                  placeholder="Type your full name"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />
                <label className="flex items-start gap-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={signatureAck}
                    onChange={(e) => setSignatureAck(e.target.checked)}
                    className="mt-0.5"
                  />
                  <span>
                    I certify this review action and accept audit recording of my
                    name and timestamp.
                  </span>
                </label>
              </div>
              {actionError ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {actionError}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                {actions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    disabled={busy}
                    onClick={() => runAction(action)}
                    className={[
                      "rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60",
                      action === "REJECT" || action === "RETURN"
                        ? "bg-rose-600"
                        : action === "APPROVE"
                          ? "bg-emerald-600"
                          : "bg-au-navy",
                    ].join(" ")}
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-au-navy">Student Clarifications</h2>
        </div>
        {clarifications.length === 0 ? (
          <p className="px-5 py-4 text-sm text-slate-500">
            No clarifications submitted yet.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {clarifications.map((c) => (
              <li key={c.id} className="px-5 py-3 text-sm">
                <p className="font-semibold text-au-navy">{c.status}</p>
                <p className="mt-1 whitespace-pre-wrap text-slate-700">
                  {c.statement}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {c.created_at ? new Date(c.created_at).toLocaleString() : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {!isStudent ? (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-3">
            <h2 className="font-semibold text-au-navy">Review History</h2>
          </div>
          {reviews.length === 0 ? (
            <p className="px-5 py-4 text-sm text-slate-500">No reviews yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {reviews.map((r) => (
                <li key={r.id} className="px-5 py-3 text-sm">
                  <p className="font-semibold text-au-navy">
                    {r.action} · {r.reviewer_role}
                  </p>
                  <p className="text-slate-600">{r.remarks || "—"}</p>
                  {r.signer_name ? (
                    <p className="mt-1 text-xs text-slate-500">
                      Signed: {r.signer_name}
                      {r.signed_at
                        ? ` · ${new Date(r.signed_at).toLocaleString()}`
                        : ""}
                    </p>
                  ) : null}
                  <p className="mt-1 text-xs text-slate-400">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-au-navy">Evidence</h2>
        </div>
        {evidence.length === 0 ? (
          <p className="px-5 py-4 text-sm text-slate-500">No evidence attached.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {evidence.map((e) => (
              <li key={e.id} className="px-5 py-3 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-au-navy">
                      {e.evidence_type}
                      {e.detection_id ? (
                        <span className="ml-2 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-violet-800">
                          AI detection #{e.detection_id}
                        </span>
                      ) : null}
                    </p>
                    <p className="truncate text-xs text-slate-500">{e.file_path}</p>
                    <p className="text-xs text-slate-400">
                      {e.created_at
                        ? new Date(e.created_at).toLocaleString()
                        : ""}
                      {e.confidence != null
                        ? ` · conf ${(e.confidence * 100).toFixed(0)}%`
                        : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-3">
                    <button
                      type="button"
                      className="text-xs font-semibold text-au-blue hover:underline"
                      onClick={async () => {
                        try {
                          await openEvidenceFile(e.id);
                        } catch (err) {
                          setError(err.message || "Could not open evidence");
                        }
                      }}
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      className="text-xs font-semibold text-slate-700 hover:underline"
                      onClick={async () => {
                        try {
                          await downloadEvidenceFile(e.id);
                        } catch (err) {
                          setError(err.message || "Could not download evidence");
                        }
                      }}
                    >
                      Download
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
