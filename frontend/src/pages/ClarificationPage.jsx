import { formatDateTime } from "../config/dateTime";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import {
  formatStatusLabel,
  formatViolationLabel,
} from "../config/casePresentation";
import {
  fetchCases,
  fetchClarifications,
  submitClarification,
} from "../services/api";

function clarifiedIdSet(clarifications) {
  const set = new Set();
  for (const row of clarifications || []) {
    if (row?.case_id != null) set.add(Number(row.case_id));
  }
  return set;
}

function pickEligibleCaseId(cases, clarifications, preferred) {
  const clarified = clarifiedIdSet(clarifications);
  const eligible = (cases || []).filter((c) => !clarified.has(Number(c.id)));
  if (
    preferred &&
    eligible.some((c) => String(c.id) === String(preferred))
  ) {
    return String(preferred);
  }
  return eligible[0]?.id != null ? String(eligible[0].id) : "";
}

export default function ClarificationPage() {
  const [searchParams] = useSearchParams();
  const presetCaseId = searchParams.get("case_id") || "";
  const navigate = useNavigate();

  const [cases, setCases] = useState([]);
  const [mine, setMine] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    case_id: presetCaseId,
    statement: "",
  });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [caseList, clarifications] = await Promise.all([
        fetchCases(),
        fetchClarifications(),
      ]);
      const safeCases = Array.isArray(caseList) ? caseList : [];
      const safeMine = Array.isArray(clarifications) ? clarifications : [];
      setCases(safeCases);
      setMine(safeMine);
      setForm((prev) => ({
        ...prev,
        case_id: pickEligibleCaseId(
          safeCases,
          safeMine,
          prev.case_id || presetCaseId
        ),
      }));
    } catch {
      setError("Unable to load required actions. Please try again.");
      setCases([]);
      setMine([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetCaseId]);

  const clarifiedCaseIds = useMemo(() => clarifiedIdSet(mine), [mine]);

  const eligibleCases = useMemo(
    () => cases.filter((c) => !clarifiedCaseIds.has(Number(c.id))),
    [cases, clarifiedCaseIds]
  );

  const presetAlreadyClarified =
    Boolean(presetCaseId) && clarifiedCaseIds.has(Number(presetCaseId));

  const selectedCase = useMemo(
    () => cases.find((c) => String(c.id) === String(form.case_id)),
    [cases, form.case_id]
  );

  const caseLabelById = useMemo(() => {
    const map = {};
    for (const c of cases) {
      map[c.id] = c.case_number || `Case #${c.id}`;
    }
    return map;
  }, [cases]);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (form.statement.trim().length < 10) {
      setError("Please write at least 10 characters for the clarification statement.");
      return;
    }
    if (!form.case_id) {
      setError("Select a UFM case before submitting.");
      return;
    }
    if (clarifiedCaseIds.has(Number(form.case_id))) {
      setError("Clarification already submitted.");
      return;
    }
    setSubmitting(true);
    try {
      const result = await submitClarification({
        case_id: Number(form.case_id),
        statement: form.statement.trim(),
      });
      const caseLabel =
        caseLabelById[result?.case_id] ||
        caseLabelById[form.case_id] ||
        `Case #${form.case_id}`;
      setMessage(
        `Clarification submitted for ${caseLabel}${
          result?.status ? ` · Status: ${formatStatusLabel(result.status)}` : ""
        }.`
      );
      setForm((prev) => ({ ...prev, statement: "" }));
      await load();
    } catch (err) {
      setError(err.message || "Unable to submit clarification. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading required actions…" />;
  }

  const canSubmit = eligibleCases.length > 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        breadcrumb="Home / Clarification / Required Actions"
        title="Clarification / Required Actions"
        description="Submit written clarification for a linked UFM case. Submissions form part of the case record."
      />

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          <p className="font-semibold">Unable to complete this action.</p>
          <p className="mt-1">{error}</p>
          {cases.length === 0 && !message ? (
            <button
              type="button"
              onClick={() => load()}
              className="mt-3 rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-red-800 ring-1 ring-red-200"
            >
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      {message ? (
        <div
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
        >
          <p className="font-semibold">Clarification recorded</p>
          <p className="mt-1">{message}</p>
        </div>
      ) : null}

      {presetAlreadyClarified ? (
        <div
          role="status"
          className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
        >
          <p className="font-semibold text-au-navy">
            Clarification already submitted.
          </p>
          <p className="mt-1">
            {caseLabelById[Number(presetCaseId)] || `Case #${presetCaseId}`}{" "}
            already has a clarification on record. An additional clarification
            cannot be submitted for this case.
          </p>
          <Link
            to={`/app/cases/${presetCaseId}`}
            className="mt-2 inline-block font-semibold text-au-blue hover:underline"
          >
            View case details
          </Link>
        </div>
      ) : null}

      {cases.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-8 text-center shadow-sm">
          <p className="text-lg font-semibold text-au-navy">
            No actions are currently required.
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
            There are no UFM cases linked to this student profile at present.
            Filed cases appear here and under UFM Case Status.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Link
              to="/app/cases"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              UFM Case Status
            </Link>
            <Link
              to="/app/help"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Help and Guidance
            </Link>
          </div>
        </div>
      ) : !canSubmit ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-8 text-center shadow-sm">
          <p className="text-lg font-semibold text-au-navy">
            Clarification already submitted.
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
            Every linked UFM case already has a clarification. Review submissions
            below or open UFM Case Status for case details.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Link
              to="/app/cases"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              My Cases
            </Link>
          </div>
        </div>
      ) : (
        <>
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            <p className="font-semibold">Clarification available</p>
            <p className="mt-1">
              {eligibleCases.length} UFM case
              {eligibleCases.length === 1 ? "" : "s"} still require clarification.
              Select a case and submit below.
            </p>
          </div>

          <form
            onSubmit={onSubmit}
            className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
            noValidate
          >
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                UFM case
              </span>
              <select
                required
                value={form.case_id}
                onChange={(e) =>
                  setForm((p) => ({ ...p, case_id: e.target.value }))
                }
                className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
              >
                {eligibleCases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_number} — {formatViolationLabel(c.violation_type)} (
                    {formatStatusLabel(c.status)})
                  </option>
                ))}
              </select>
            </label>

            {selectedCase ? (
              <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-3 text-sm text-slate-600">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={selectedCase.status} />
                  <span>
                    {selectedCase.exam_course_code || "Examination"}
                    {selectedCase.exam_date
                      ? ` · ${selectedCase.exam_date}`
                      : ""}
                  </span>
                </div>
                <Link
                  to={`/app/cases/${selectedCase.id}`}
                  className="mt-2 inline-block font-semibold text-au-blue hover:underline"
                >
                  View case details
                </Link>
              </div>
            ) : null}

            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                Clarification statement
              </span>
              <textarea
                required
                rows={8}
                value={form.statement}
                onChange={(e) =>
                  setForm((p) => ({ ...p, statement: e.target.value }))
                }
                placeholder="Describe the circumstances and any context for review…"
                className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
                aria-describedby="clarification-hint"
              />
              <span id="clarification-hint" className="mt-1 block text-xs text-slate-500">
                Minimum 10 characters. The statement is saved to the case record.
                One clarification per case.
              </span>
            </label>

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={submitting || !form.case_id}
                className="rounded-xl bg-au-navy px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {submitting ? "Submitting…" : "Submit clarification"}
              </button>
              <button
                type="button"
                onClick={() => navigate("/app/cases")}
                className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700"
              >
                Back to My Cases
              </button>
            </div>
          </form>
        </>
      )}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-au-navy">
            Submitted clarifications
          </h2>
        </div>
        {mine.length === 0 ? (
          <p className="px-5 py-4 text-sm text-slate-500">
            No clarifications have been submitted yet.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {mine.map((c) => (
              <li key={c.id} className="px-5 py-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-au-navy">
                      {caseLabelById[c.case_id] || `Case #${c.case_id}`}
                    </p>
                    <StatusBadge status={c.status} />
                  </div>
                  <p className="text-xs text-slate-400">
                    {c.created_at
                      ? formatDateTime(c.created_at)
                      : ""}
                  </p>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-slate-700">
                  {c.statement}
                </p>
                <Link
                  to={`/app/cases/${c.case_id}`}
                  className="mt-2 inline-block text-xs font-semibold text-au-blue hover:underline"
                >
                  Open case
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
