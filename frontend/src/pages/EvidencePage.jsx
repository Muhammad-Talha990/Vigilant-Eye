import { formatDateTime } from "../config/dateTime";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import EvidenceFileActions from "../components/EvidenceFileActions";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import LoadingState from "../components/LoadingState";
import {
  evidenceHasAiSignal,
  evidenceSourceLabel,
  fileNameFromPath,
  formatEvidenceTypeLabel,
  formatViolationLabel,
} from "../config/casePresentation";
import {
  EVIDENCE_UPLOAD_ROLES,
  EVIDENCE_VIEW_ROLES,
  roleIn,
} from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";
import {
  fetchCases,
  fetchEvidence,
  loadEvidenceObjectUrl,
  uploadEvidence,
} from "../services/api";

const EVIDENCE_TYPES = ["SNAPSHOT", "VIDEO_CLIP", "DOCUMENT"];

export default function EvidencePage() {
  const { user } = useAuth();
  const canView = roleIn(user?.role, EVIDENCE_VIEW_ROLES);
  const canUpload = roleIn(user?.role, EVIDENCE_UPLOAD_ROLES);
  const [searchParams, setSearchParams] = useSearchParams();
  const presetCaseId = searchParams.get("case_id") || "";

  const [items, setItems] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [preview, setPreview] = useState(null); // { url, mime, filename } | null | 'loading' | 'unsupported'
  const [form, setForm] = useState({
    case_id: presetCaseId,
    evidence_type: "SNAPSHOT",
    seat_location: "",
    confidence: "",
    file: null,
  });

  const casesById = useMemo(() => {
    const map = {};
    for (const c of cases) map[c.id] = c;
    return map;
  }, [cases]);

  const caseLabel = (caseId) => {
    const c = casesById[caseId];
    if (!c) return caseId != null ? `Case #${caseId}` : "—";
    return c.case_number || `Case #${caseId}`;
  };

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [evidence, caseList] = await Promise.all([
        fetchEvidence(presetCaseId || null),
        fetchCases(),
      ]);
      setItems(Array.isArray(evidence) ? evidence : []);
      setCases(Array.isArray(caseList) ? caseList : []);
      setForm((prev) => ({
        ...prev,
        case_id:
          prev.case_id ||
          presetCaseId ||
          (caseList?.[0]?.id ? String(caseList[0].id) : ""),
      }));
    } catch {
      setError("Unable to load evidence. Please try again.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      return;
    }
    load();
  }, [presetCaseId, canView]);

  useEffect(() => {
    return () => {
      if (preview?.url) URL.revokeObjectURL(preview.url);
    };
  }, [preview]);

  const typeOptions = useMemo(() => {
    const set = new Set(items.map((e) => e.evidence_type).filter(Boolean));
    return [...set].sort();
  }, [items]);

  const filtered = useMemo(() => {
    if (!typeFilter) return items;
    return items.filter((e) => e.evidence_type === typeFilter);
  }, [items, typeFilter]);

  const selected = useMemo(
    () => filtered.find((e) => e.id === selectedId) || null,
    [filtered, selectedId]
  );

  const presetCase = presetCaseId ? casesById[Number(presetCaseId)] : null;

  async function showPreview(evidenceId) {
    if (preview?.url) URL.revokeObjectURL(preview.url);
    setSelectedId(evidenceId);
    setPreview("loading");
    try {
      const loaded = await loadEvidenceObjectUrl(evidenceId, { preview: true });
      const mime = loaded.mime || "";
      if (
        mime.startsWith("image/") ||
        mime.startsWith("video/") ||
        mime === "application/pdf"
      ) {
        setPreview(loaded);
      } else {
        URL.revokeObjectURL(loaded.url);
        setPreview("unsupported");
      }
    } catch {
      setPreview("unsupported");
    }
  }

  function onCaseFilterChange(value) {
    if (!value) setSearchParams({});
    else setSearchParams({ case_id: value });
  }

  async function onSubmit(event) {
    event.preventDefault();
    setMessage("");
    setError("");
    if (!canUpload) {
      setError("Your role is not authorized to upload evidence.");
      return;
    }
    if (!form.file) {
      setError("Choose a file to upload.");
      return;
    }
    if (!form.case_id) {
      setError("Select the UFM case this evidence belongs to.");
      return;
    }
    setSubmitting(true);
    try {
      const body = new FormData();
      body.append("case_id", form.case_id);
      body.append("evidence_type", form.evidence_type);
      body.append("file", form.file);
      if (form.seat_location.trim()) {
        body.append("seat_location", form.seat_location.trim());
      }
      if (form.confidence !== "") {
        body.append("confidence", form.confidence);
      }
      await uploadEvidence(body);
      setMessage(
        `Evidence uploaded successfully for ${caseLabel(Number(form.case_id))}.`
      );
      setForm((prev) => ({
        ...prev,
        file: null,
        seat_location: "",
        confidence: "",
      }));
      const fileInput = document.getElementById("evidence-file-input");
      if (fileInput) fileInput.value = "";
      await load();
    } catch (err) {
      setError(err.message || "Upload failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!canView) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <p className="font-semibold">Evidence library is not available</p>
        <p className="mt-1">
          The institutional evidence library is limited to authorized staff.
          Case evidence appears on the case detail page when provided.
        </p>
        <Link
          to="/app/cases"
          className="mt-3 inline-flex text-sm font-semibold text-au-blue"
        >
          ← My Cases
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5">
      <PageHeader
        breadcrumb="Home / Cases / Evidence"
        title="Evidence Management"
        description={
          presetCase
            ? `Evidence associated with UFM case ${presetCase.case_number}.`
            : "Review examination evidence associated with reported UFM cases."
        }
        actions={
          <div className="flex max-w-full flex-wrap items-center gap-2">
            <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm text-slate-600">
              Case
              <select
                value={presetCaseId}
                onChange={(e) => onCaseFilterChange(e.target.value)}
                className="portal-select w-auto max-w-[14rem]"
              >
                <option value="">All cases</option>
                {cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_number}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm text-slate-600">
              Type
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="portal-select w-auto max-w-[12rem]"
              >
                <option value="">All types</option>
                {(typeOptions.length ? typeOptions : EVIDENCE_TYPES).map((t) => (
                  <option key={t} value={t}>
                    {formatEvidenceTypeLabel(t)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        }
      />

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p className="font-semibold">Unable to complete evidence action.</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : null}
      {message ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}

      {canUpload ? (
        <form
          onSubmit={onSubmit}
          className="space-y-4 portal-card p-5"
        >
          <div>
            <h2 className="font-semibold text-au-navy">Upload evidence</h2>
            <p className="mt-1 text-sm text-slate-600">
              Attach a file to an existing UFM case. The upload is stored against
              that case only.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
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
                className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5"
              >
                {cases.length === 0 ? (
                  <option value="">No cases available</option>
                ) : (
                  cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.case_number} — {formatViolationLabel(c.violation_type)}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                Evidence type
              </span>
              <select
                value={form.evidence_type}
                onChange={(e) =>
                  setForm((p) => ({ ...p, evidence_type: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5"
              >
                {EVIDENCE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {formatEvidenceTypeLabel(t)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                Seat (optional)
              </span>
              <input
                value={form.seat_location}
                onChange={(e) =>
                  setForm((p) => ({ ...p, seat_location: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5"
                placeholder="A12"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                System confidence (optional)
              </span>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={form.confidence}
                onChange={(e) =>
                  setForm((p) => ({ ...p, confidence: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5"
                placeholder="0.91"
              />
              <span className="mt-1 block text-[11px] text-slate-500">
                Optional system-assisted value only — not a disciplinary finding.
              </span>
            </label>
            <div className="block text-sm sm:col-span-2">
              <span className="mb-1 block font-medium text-slate-700">File</span>
              <label
                htmlFor="evidence-file-input"
                className="btn-secondary flex w-full cursor-pointer justify-start gap-2 overflow-hidden"
              >
                <input
                  id="evidence-file-input"
                  type="file"
                  required
                  className="sr-only"
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      file: e.target.files?.[0] || null,
                    }))
                  }
                />
                <span className="shrink-0 rounded bg-sky-100 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-au-navy">
                  Choose file
                </span>
                <span className="truncate font-medium text-slate-700">
                  {form.file
                    ? form.file.name
                    : "No file chosen — click to browse"}
                </span>
              </label>
              {form.file ? (
                <span className="mt-1 block text-xs text-slate-600">
                  Selected: {form.file.name} (
                  {Math.max(1, Math.round(form.file.size / 1024))} KB)
                </span>
              ) : (
                <span className="mt-1 block text-xs text-slate-500">
                  No file selected.
                </span>
              )}
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting || !cases.length}
            className="btn-primary"
          >
            {submitting ? "Uploading…" : "Upload evidence"}
          </button>
        </form>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          This role can view case evidence. Uploading new evidence is limited to
          Invigilator accounts that file UFM incidents.
        </div>
      )}

      <div className="portal-split">
        <section className="portal-card overflow-hidden">
          <div className="border-b border-slate-100 px-5 py-3">
            <h2 className="font-semibold text-au-navy">Evidence records</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {loading
                ? "Loading…"
                : `${filtered.length} record${filtered.length === 1 ? "" : "s"}`}
              <span className="text-slate-400">
                {" "}
                · File name and upload metadata appear in Evidence detail
              </span>
            </p>
          </div>
          {loading ? (
            <div className="px-6 py-10 text-center">
              <p className="font-medium text-au-navy">Loading evidence…</p>
              <p className="mt-1 text-sm text-slate-500">
                Retrieving case-linked files.
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-6 py-10 text-center">
              <p className="font-semibold text-au-navy">No evidence to show</p>
              <p className="mt-1 text-sm text-slate-600">
                {presetCaseId
                  ? "No evidence is attached to this UFM case yet."
                  : typeFilter
                    ? "No evidence matches this type filter."
                    : "No evidence has been uploaded yet."}
              </p>
            </div>
          ) : (
            <>
              <div className="portal-data-cards">
                {filtered.map((e) => {
                  const active = selectedId === e.id;
                  return (
                    <div
                      key={e.id}
                      className={[
                        "portal-case-card",
                        active ? "ring-2 ring-au-blue/30" : "",
                      ].join(" ")}
                      data-affordance="static"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="portal-case-card-title">#{e.id}</p>
                        <span className="text-xs font-semibold text-slate-600">
                          {formatEvidenceTypeLabel(e.evidence_type)}
                        </span>
                      </div>
                      <p className="portal-case-card-meta">
                        {e.case_id != null ? (
                          <Link
                            to={`/app/cases/${e.case_id}`}
                            className="font-medium text-au-blue hover:underline"
                          >
                            {caseLabel(e.case_id)}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </p>
                      <p className="portal-case-card-meta cell-wrap">
                        {evidenceSourceLabel(e)}
                      </p>
                      <p className="portal-case-card-meta">
                        {e.timestamp
                          ? formatDateTime(e.timestamp)
                          : "—"}
                      </p>
                      <div className="mt-3">
                        <EvidenceFileActions
                          evidenceId={e.id}
                          showPreview
                          onPreview={showPreview}
                          onError={(msg) => setError(msg)}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="portal-table-wrap portal-table-desktop">
                <table className="portal-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Case</th>
                      <th>Type</th>
                      <th>Source</th>
                      <th className="col-hide-md">Captured</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((e) => {
                      const active = selectedId === e.id;
                      return (
                        <tr
                          key={e.id}
                          className={active ? "bg-slate-50" : undefined}
                        >
                          <td className="font-semibold text-au-navy">#{e.id}</td>
                          <td>
                            {e.case_id != null ? (
                              <Link
                                to={`/app/cases/${e.case_id}`}
                                className="font-medium text-au-blue hover:underline"
                              >
                                {caseLabel(e.case_id)}
                              </Link>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td>{formatEvidenceTypeLabel(e.evidence_type)}</td>
                          <td className="cell-wrap text-xs text-slate-600">
                            {evidenceSourceLabel(e)}
                          </td>
                          <td className="col-hide-md text-xs text-slate-500">
                            {e.timestamp
                              ? formatDateTime(e.timestamp)
                              : "—"}
                          </td>
                          <td>
                            <EvidenceFileActions
                              evidenceId={e.id}
                              showPreview
                              onPreview={showPreview}
                              onError={(msg) => setError(msg)}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        <aside className="portal-card portal-split-detail h-fit p-4">
          <h2 className="font-semibold text-au-navy">Evidence detail</h2>
          {!selected ? (
            <p className="mt-3 text-sm text-slate-500">
              Select Preview on a record to inspect metadata and an in-browser
              preview when the file type is supported.
            </p>
          ) : (
            <div className="mt-3 space-y-3 text-sm">
              <dl className="grid gap-2">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Evidence ID
                  </dt>
                  <dd className="font-medium">#{selected.id}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Case
                  </dt>
                  <dd className="font-medium">
                    {selected.case_id != null ? (
                      <Link
                        to={`/app/cases/${selected.case_id}`}
                        className="text-au-blue hover:underline"
                      >
                        {caseLabel(selected.case_id)}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Type
                  </dt>
                  <dd>{formatEvidenceTypeLabel(selected.evidence_type)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Source
                  </dt>
                  <dd className="text-slate-700 cell-wrap">
                    {evidenceSourceLabel(selected)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    File name
                  </dt>
                  <dd className="break-all text-slate-700">
                    {fileNameFromPath(selected.file_path) || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Captured
                  </dt>
                  <dd className="text-slate-700">
                    {selected.timestamp
                      ? formatDateTime(selected.timestamp)
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Uploaded
                  </dt>
                  <dd className="text-slate-700">
                    {selected.created_at
                      ? formatDateTime(selected.created_at)
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Uploaded by
                  </dt>
                  <dd className="text-slate-700">
                    {selected.uploaded_by != null
                      ? `User #${selected.uploaded_by}`
                      : "—"}
                  </dd>
                </div>
                {selected.seat_location ? (
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-slate-500">
                      Seat
                    </dt>
                    <dd>{selected.seat_location}</dd>
                  </div>
                ) : null}
              </dl>

              {evidenceHasAiSignal(selected) ? (
                <div className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-900">
                  <p className="font-semibold">
                    System-assisted / AI-generated information
                  </p>
                  <p className="mt-1">
                    Detection links and confidence values are review aids only.
                    They are not a final finding of misconduct.
                  </p>
                </div>
              ) : null}

              <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                {preview === "loading" ? (
                  <p className="px-3 py-8 text-center text-xs text-slate-500">
                    Loading preview…
                  </p>
                ) : preview === "unsupported" ? (
                  <p className="px-3 py-6 text-center text-xs text-slate-600">
                    In-browser preview is not available for this file type. Use
                    Open or Download.
                  </p>
                ) : preview?.mime?.startsWith("image/") ? (
                  <img
                    src={preview.url}
                    alt={`Evidence #${selected.id}`}
                    className="max-h-56 w-full object-contain"
                  />
                ) : preview?.mime?.startsWith("video/") ? (
                  <video
                    src={preview.url}
                    controls
                    className="max-h-56 w-full bg-black"
                  />
                ) : preview?.mime === "application/pdf" ? (
                  <iframe
                    title={`Evidence #${selected.id}`}
                    src={preview.url}
                    className="h-56 w-full"
                  />
                ) : (
                  <p className="px-3 py-6 text-center text-xs text-slate-500">
                    No preview loaded.
                  </p>
                )}
              </div>

              <EvidenceFileActions
                evidenceId={selected.id}
                onError={(msg) => setError(msg)}
              />
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
